"""Getting up from a table, and sitting down at one that is already going.

Both of these used to fall in the same hole: ``lobbies.leave`` takes you off the
member list *before* the lobby broadcasts anything, so a leaver receives nothing
at all - and a join into a running game was only ever answered with a lobby row,
never with the table. From the player's side the first looked like the button
was dead and the second like the client was stuck on the lobby page.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tests.e2e.conftest import ScriptedClient, answer_prompt


async def seat_four(server: str) -> tuple[list[ScriptedClient], str]:
    """Four seated clients, plus the lobby id.

    The id is handed back rather than dug out of a snapshot later: the snapshot
    stopped carrying the lobby when the protocol was slimmed down, and only
    ``lobby_state`` has it.
    """
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()
    await clients[0].send(
        "lobby_create", name="Tafel", ruleset="klassiek", scoring="kaartclubs", rng_seed=3
    )
    state = await clients[0].wait_for("lobby_state")
    lobby_id = state["lobby"]["id"]
    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=lobby_id)
        await client.wait_for("lobby_state")
    return clients, lobby_id


async def deal_a_hand(clients: list[ScriptedClient], *, timeout: float = 30.0) -> None:
    """Play far enough that everyone holds cards and the table is live."""
    dealt = set()
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
            if snapshot["contract"] is not None:
                dealt.add(client.username)
                if len(dealt) == len(clients):
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


async def test_leaving_a_table_answers_the_leaver(server: str) -> None:
    """The whole bug in one assertion: something must come back."""
    clients, _ = await seat_four(server)
    try:
        jan = clients[0]
        await jan.send("lobby_leave")
        listing = await jan.wait_for("lobby_list", timeout=10)
        assert "lobbies" in listing
    finally:
        for client in clients:
            await client.close()


async def test_the_others_are_told_who_left(server: str) -> None:
    clients, _ = await seat_four(server)
    try:
        jan, piet = clients[0], clients[1]
        await jan.send("lobby_leave")
        left = await piet.wait_for("player_left", timeout=10)
        assert left["username"] == "Jan"
        state = await piet.wait_for("lobby_state", timeout=10)
        assert "Jan" not in [member["username"] for member in state["lobby"]["members"]]
    finally:
        for client in clients:
            await client.close()


async def test_taking_a_free_seat_mid_game_puts_you_at_the_table(server: str) -> None:
    """A join into a running game must deal you in, not leave you in the list."""
    clients, lobby_id = await seat_four(server)
    try:
        await deal_a_hand(clients)
        korneel = clients[3]
        await korneel.send("lobby_leave")
        await korneel.wait_for("lobby_list", timeout=10)

        # Back to the same table, which is still mid-round.
        await korneel.send("lobby_join", lobby_id=lobby_id)
        started = await korneel.wait_for("game_started", timeout=10)
        assert started["your_seat"] is not None
        snapshot = await korneel.wait_for("snapshot", timeout=10)
        assert snapshot["snapshot"]["contract"] is not None, "de ronde loopt nog"
        assert snapshot["snapshot"]["your_seat"] is not None
    finally:
        for client in clients:
            await client.close()


async def test_a_table_does_not_stay_paused_on_somebody_who_left(server: str) -> None:
    """Dropping out and then leaving used to strand the other three forever.

    ``remove_member`` takes the name off the missing list, so the pause had
    nothing left to wait for and nothing to lift it either.
    """
    clients, _ = await seat_four(server)
    try:
        await deal_a_hand(clients)
        jan, korneel = clients[0], clients[3]

        await korneel.close()
        await jan.wait_for("game_paused", timeout=15)

        # He comes back but decides not to play, and leaves for good.
        back = ScriptedClient(server, "Korneel")
        await back.__aenter__()
        await back.send("lobby_leave")
        await back.wait_for("lobby_list", timeout=10)

        resumed = await jan.wait_for(
            "snapshot", predicate=lambda m: not m["snapshot"]["paused"], timeout=15
        )
        assert resumed["snapshot"]["paused"] is False
        await back.close()
    finally:
        for client in clients:
            await client.close()
