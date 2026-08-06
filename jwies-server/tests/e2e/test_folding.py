"""The declaring side gives up a lost round, over a real websocket.

The engine's own rules are covered in ``tests/core/test_folding.py``. What is
only testable here is the wiring: that ``fold`` survives the trip through the
protocol models and the lobby queue, that the offer reaches the declaring side
and nobody else, and that the table really does roll into the next round.

It plays on the ``vlak`` scale, whose penalty does not depend on how short the
declaring side finished, so conceding here costs nothing - which keeps these
tests about the plumbing rather than the arithmetic.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from tests.e2e.conftest import ScriptedClient, answer_prompt

#: Seed 0 deals a contract with a single declarer, who settles the round the
#: moment he presses. Seed 58 deals a troel - two declarers, so there is a
#: partner to wait for and a vote to take back.
PAIRED_SEED = 58


async def seat_four(server: str, *, rng_seed: int = 0) -> list[ScriptedClient]:
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()

    await clients[0].send(
        "lobby_create", name="Vouwtafel", ruleset="klassiek", scoring="vlak", rng_seed=rng_seed
    )
    state = await clients[0].wait_for("lobby_state")
    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=state["lobby"]["id"])
        await client.wait_for("lobby_state")
    return clients


async def play_until_offered(clients: list[ScriptedClient], *, timeout: float = 60.0) -> None:
    """Drive the table until the declaring side is offered the way out.

    Every pump stops the moment anyone sees the offer. The declaring side then
    answers no more prompts, so the round cannot run away from under the test
    while it is making its assertions.
    """
    offered = asyncio.Event()

    async def pump(client: ScriptedClient) -> None:
        answered: dict[str, Any] | None = None
        while not offered.is_set():
            try:
                message = await client._recv(timeout=1.0)
            except TimeoutError:
                continue
            if message["type"] != "snapshot":
                continue
            snapshot = message["snapshot"]
            if snapshot["folding_offered"]:
                offered.set()
                return
            prompt = snapshot.get("prompt")
            if prompt is not None and prompt != answered:
                answered = prompt
                await answer_prompt(client, prompt)

    tasks = [asyncio.create_task(pump(client)) for client in clients]
    try:
        await asyncio.wait_for(offered.wait(), timeout=timeout)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def declaring(clients: list[ScriptedClient]) -> list[ScriptedClient]:
    """The clients holding the contract, per the last snapshot they saw."""
    contract = next(
        client.snapshot["contract"] for client in clients if client.snapshot.get("contract")
    )
    seats = set(contract["declarers"])
    return [client for client in clients if client.snapshot["your_seat"] in seats]


def defending(clients: list[ScriptedClient]) -> list[ScriptedClient]:
    on_the_contract = {client.username for client in declaring(clients)}
    return [client for client in clients if client.username not in on_the_contract]


async def give_up_together(clients: list[ScriptedClient]) -> dict[str, Any]:
    """Every declarer presses; hands back the snapshot of the next round."""
    declarers = declaring(clients)
    before = declarers[0].snapshot["round_number"]

    # A partner who has not agreed yet keeps the round alive.
    for count, client in enumerate(declarers[:-1], start=1):
        await client.send("fold", fold=True)
        await declarers[0].wait_for(
            "snapshot",
            predicate=lambda m, n=count: len(m["snapshot"]["folded"]) == n,
            timeout=15,
        )
        assert declarers[0].snapshot["round_number"] == before

    # The last of them ends it, and the next round is dealt.
    await declarers[-1].send("fold", fold=True)
    after = await declarers[0].wait_for(
        "snapshot",
        predicate=lambda m: m["snapshot"]["round_number"] > before,
        timeout=15,
    )
    return dict(after["snapshot"])


async def test_a_lone_declarer_gives_up_on_his_own(server: str) -> None:
    clients = await seat_four(server)
    try:
        await play_until_offered(clients)
        declarers = declaring(clients)
        assert len(declarers) == 1, "dit zaad hoort een contract van een speler te geven"

        # The offer is addressed to the declaring side and to nobody else.
        assert declarers[0].snapshot["folding_offered"] is True
        assert declarers[0].snapshot["folded"] == []
        for client in defending(clients):
            assert client.snapshot["folding_offered"] is False

        after = await give_up_together(clients)
        assert after["folding_offered"] is False
        assert after["folded"] == []
        assert after["contract"] is None
        assert sum(Decimal(value) for value in after["totals"].values()) == 0
    finally:
        for client in clients:
            await client.close()


async def test_a_pair_needs_both_partners(server: str) -> None:
    """One of the two is not enough: conceding costs the partner points too."""
    clients = await seat_four(server, rng_seed=PAIRED_SEED)
    try:
        await play_until_offered(clients)
        assert len(declaring(clients)) == 2, "dit zaad hoort een troel te geven"

        after = await give_up_together(clients)
        assert after["contract"] is None
        assert sum(Decimal(value) for value in after["totals"].values()) == 0
    finally:
        for client in clients:
            await client.close()


async def test_a_defender_is_refused(server: str) -> None:
    """It is not their contract to concede, and the server says so."""
    clients = await seat_four(server)
    try:
        await play_until_offered(clients)
        defender = defending(clients)[0]

        await defender.send("fold", fold=True)
        error = await defender.wait_for("error", timeout=15)
        assert error["code"] == "illegal_move"
        assert "spelende partij" in error["text"]
    finally:
        for client in clients:
            await client.close()


async def test_a_vote_can_be_taken_back(server: str) -> None:
    clients = await seat_four(server, rng_seed=PAIRED_SEED)
    try:
        await play_until_offered(clients)
        declarers = declaring(clients)
        assert len(declarers) == 2, "dit zaad hoort een troel te geven"
        first = declarers[0]

        await first.send("fold", fold=True)
        await first.wait_for(
            "snapshot", predicate=lambda m: m["snapshot"]["folded"] != [], timeout=15
        )
        await first.send("fold", fold=False)
        withdrawn = await first.wait_for(
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
