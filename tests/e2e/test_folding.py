"""Four clients agree to stop a lost round, over a real websocket.

The engine's own rules are covered in ``tests/core/test_folding.py``. What is
only testable here is the wiring: that ``fold`` survives the trip through the
protocol models and the lobby queue, that the offer and the tally reach every
seat in the snapshot, and that the table really does roll into the next round.

It plays on the ``vlak`` scale, whose penalty does not depend on how short the
declaring side finished. That is the only configuration in which the offer
appears before the last trick - see the module docstring of the core tests.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tests.e2e.conftest import ScriptedClient, answer_prompt


async def seat_four(server: str) -> list[ScriptedClient]:
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()

    await clients[0].send(
        "lobby_create", name="Vouwtafel", ruleset="klassiek", scoring="vlak", rng_seed=0
    )
    state = await clients[0].wait_for("lobby_state")
    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=state["lobby"]["id"])
        await client.wait_for("lobby_state")
    return clients


async def play_until_offered(clients: list[ScriptedClient], *, timeout: float = 60.0) -> None:
    """Drive the table until every client has been offered the fold."""
    import asyncio

    offered: set[str] = set()
    done = asyncio.Event()

    async def pump(client: ScriptedClient) -> None:
        answered: dict[str, Any] | None = None
        while not done.is_set():
            try:
                message = await client._recv(timeout=1.0)
            except TimeoutError:
                continue
            if message["type"] != "snapshot":
                continue
            snapshot = message["snapshot"]
            if snapshot["folding_offered"]:
                offered.add(client.username)
                if len(offered) == len(clients):
                    done.set()
                return
            prompt = snapshot.get("prompt")
            if prompt is not None and prompt != answered:
                answered = prompt
                await answer_prompt(client, prompt)

    tasks = [asyncio.create_task(pump(client)) for client in clients]
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_the_table_can_stop_a_lost_round(server: str) -> None:
    clients = await seat_four(server)
    try:
        await play_until_offered(clients)

        # Everybody sees the same offer, and nobody has agreed yet.
        for client in clients:
            assert client.snapshot["folding_offered"] is True
            assert client.snapshot["folded"] == []
        before = clients[0].snapshot["round_number"]
        assert clients[0].snapshot["contract"] is not None

        # Three votes are not enough; the round is still running.
        for client in clients[:3]:
            await client.send("fold", fold=True)
        await clients[0].wait_for(
            "snapshot", predicate=lambda m: len(m["snapshot"]["folded"]) == 3, timeout=15
        )
        assert clients[0].snapshot["round_number"] == before

        # The fourth ends it, and the next round is dealt.
        await clients[3].send("fold", fold=True)
        after = await clients[0].wait_for(
            "snapshot",
            predicate=lambda m: m["snapshot"]["round_number"] > before,
            timeout=15,
        )
        assert after["snapshot"]["folding_offered"] is False
        assert after["snapshot"]["folded"] == []
        assert after["snapshot"]["contract"] is None
        assert sum(Decimal(value) for value in after["snapshot"]["totals"].values()) == 0
    finally:
        for client in clients:
            await client.close()


async def test_a_vote_can_be_taken_back(server: str) -> None:
    clients = await seat_four(server)
    try:
        await play_until_offered(clients)
        jan = clients[0]

        await jan.send("fold", fold=True)
        await jan.wait_for(
            "snapshot", predicate=lambda m: m["snapshot"]["folded"] != [], timeout=15
        )
        await jan.send("fold", fold=False)
        withdrawn = await jan.wait_for(
            "snapshot", predicate=lambda m: m["snapshot"]["folded"] == [], timeout=15
        )
        assert withdrawn["snapshot"]["folding_offered"] is True
    finally:
        for client in clients:
            await client.close()


async def test_folding_is_refused_before_a_contract_is_beyond_saving(server: str) -> None:
    """The client cannot talk the server into it: the engine decides."""
    clients = await seat_four(server)
    try:
        jan = clients[0]
        await jan.send("fold", fold=True)
        error = await jan.wait_for("error", timeout=15)
        assert error["code"] in ("illegal_move", "game_not_running")
    finally:
        for client in clients:
            await client.close()
