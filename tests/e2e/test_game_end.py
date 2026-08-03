"""A bounded game must actually end, and say so in the lobby list.

The shipped rulesets play forever (``aantal_rondes: 0``), so nothing else in
the suite ever reaches ``GameFinished``. This uses the ``kort`` ruleset from
the conftest, which stops after one round.
"""

from __future__ import annotations

from typing import Any

from tests.e2e.conftest import ScriptedClient, play_until


async def seat_four(server: str) -> list[ScriptedClient]:
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()

    await clients[0].send(
        "lobby_create", name="Korte tafel", ruleset="kort", scoring="schaal_a", rng_seed=42
    )
    state = await clients[0].wait_for("lobby_state")
    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=state["lobby"]["id"])
        await client.wait_for("lobby_state")
    return clients


async def test_a_finished_game_stops_advertising_itself_as_running(server: str) -> None:
    clients = await seat_four(server)
    jan = clients[0]
    try:

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            return message["type"] == "round_finished" and client.username == "Jan"

        await play_until(clients, stop, timeout=120)

        # The engine is done. Without the status transition the lobby would sit
        # at "bezig" forever, inviting people to a table that will never ask
        # anyone for anything again.
        await jan.send("lobby_leave")
        listing = await jan.wait_for("lobby_list", timeout=10)
        ours = [lobby for lobby in listing["lobbies"] if lobby["name"] == "Korte tafel"]
        assert ours, "de tafel staat niet meer in de lijst"
        assert ours[0]["status"] == "finished"
    finally:
        for client in clients:
            await client.close()
