"""A disconnect must pause the game, never end it.

This is the robustness requirement: the username is the rebinding key, the
engine is never touched while a player is away, and the returning player gets
their whole world back from one snapshot.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tests.e2e.conftest import PROTOCOL_VERSION, ScriptedClient, play_until


async def seat_four(server: str) -> list[ScriptedClient]:
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()

    await clients[0].send(
        "lobby_create", name="Testtafel", ruleset="klassiek", scoring="kaartclubs", rng_seed=7
    )
    state = await clients[0].wait_for("lobby_state")
    lobby_id = state["lobby"]["id"]
    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=lobby_id)
        await client.wait_for("lobby_state")
    return clients


async def play_a_few_tricks(clients: list[ScriptedClient], count: int = 2) -> None:
    """Get the game properly under way so there is real state to restore."""
    tricks: list[Any] = []

    def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
        if message["type"] == "trick_completed" and client.username == "Jan":
            tricks.append(message)
            return len(tricks) >= count
        return False

    await play_until(clients, stop, timeout=60)


async def test_a_disconnect_pauses_the_game_and_a_return_resumes_it(server: str) -> None:
    clients = await seat_four(server)
    jan, piet, joris, korneel = clients
    try:
        await play_a_few_tricks(clients)

        # Capture what Korneel knows, then rip his socket away mid-round.
        await korneel.send("request_snapshot")
        before = await korneel.wait_for("snapshot")
        token = korneel.resume_token
        await korneel.close()

        # The other three are told the game is paused, and by whom.
        paused = await jan.wait_for("game_paused", timeout=15)
        assert "Korneel" in paused["missing"]
        assert "Korneel" in paused["text"]
        for client in (piet, joris):
            await client.wait_for("game_paused", timeout=15)

        # While paused, moves are refused rather than silently swallowed.
        await jan.send("play_card", card="AH")
        error = await jan.wait_for("error", timeout=10)
        assert error["code"] in ("game_paused", "illegal_move")

        # Chat keeps working so people can say they are coming back.
        await piet.send("chat_send", text="even wachten op Korneel")
        chat = await piet.wait_for(
            "chat", predicate=lambda m: m.get("sender") == "Piet", timeout=10
        )
        assert chat["text"] == "even wachten op Korneel"

        # Korneel returns with the same username and his resume token.
        back = ScriptedClient(server, "Korneel")
        back.socket = None
        await back.__aenter__()
        after = await back.wait_for("snapshot", timeout=15)

        # His whole world is restored.
        assert after["snapshot"]["your_seat"] == before["snapshot"]["your_seat"]
        assert after["snapshot"]["your_hand"] == before["snapshot"]["your_hand"]
        assert after["snapshot"]["current_trick"] == before["snapshot"]["current_trick"]
        assert after["snapshot"]["trick_counts"] == before["snapshot"]["trick_counts"]
        assert after["snapshot"]["contract"] == before["snapshot"]["contract"]
        assert after["snapshot"]["bids"] == before["snapshot"]["bids"]
        assert token is not None

        # Everyone is told play continues.
        resumed = await jan.wait_for("game_resumed", timeout=15)
        assert "Korneel" in resumed["text"]

        # And the game genuinely finishes from here.
        finished: dict[str, Any] = {}

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            if message["type"] == "round_finished":
                finished[client.username] = message
                return len(finished) >= 4
            return False

        await play_until([jan, piet, joris, back], stop, timeout=90)
        assert len(finished) == 4
        await back.close()
    finally:
        for client in clients:
            await client.close()


async def test_the_outstanding_prompt_is_reissued_after_resuming(server: str) -> None:
    clients = await seat_four(server)
    jan = clients[0]
    try:
        await play_a_few_tricks(clients, count=1)

        # Find whoever is on turn and disconnect exactly them, so the pending
        # prompt is the one that must survive the round trip.
        await jan.send("request_snapshot")
        snapshot = (await jan.wait_for("snapshot"))["snapshot"]
        pending_seat = snapshot["pending_seat"]
        assert pending_seat is not None
        on_turn = next(
            client
            for client in clients
            if any(
                seat["seat"] == pending_seat and seat["username"] == client.username
                for seat in snapshot["seats"]
            )
        )
        await on_turn.close()
        await jan.wait_for("game_paused", timeout=15)

        back = ScriptedClient(server, on_turn.username)
        await back.__aenter__()
        # The engine never recorded that it had already asked, so the turn
        # simply comes back in the snapshot, legal options intact.
        restored = await back.wait_for(
            "snapshot", timeout=15, predicate=lambda m: m["snapshot"]["prompt"] is not None
        )
        assert restored["snapshot"]["prompt"]["kind"] in ("play", "bid", "cut", "shuffle")
        await back.close()
    finally:
        for client in clients:
            await client.close()


async def test_an_outdated_client_is_told_to_update(server: str) -> None:
    """Not "onbegrijpelijk bericht" - that is what the version number is for.

    The trap this guards: a client one version behind is also sending fields the
    current models have dropped, so validating the envelope before reading ``v``
    answers "unparseable" and the player learns nothing. This is a real v1
    handshake, ``id`` and ``client`` included.
    """
    import json

    import websockets

    async with websockets.connect(server) as socket:
        await socket.send(
            json.dumps(
                {"v": 1, "id": "7", "msg": {"type": "hello", "username": "Jan", "client": "qt"}}
            )
        )
        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))["msg"]

    assert message["type"] == "error"
    assert message["code"] == "protocol_version"
    assert "versie 1" in message["text"] and "versie 2" in message["text"]


async def test_a_refused_name_says_which_rule_it_broke(server: str) -> None:
    """Not "onbegrijpelijk bericht" either - the server knows exactly what is wrong.

    The trap this guards: ``Hello.username`` used to carry the constrained
    ``Username`` type, so a name outside the pattern failed validation of the
    whole envelope and came back as ``bad_message``. The friendly branch in
    ``_handshake`` was unreachable, and the player saw a sentence about an
    unreadable message for the crime of typing one letter. Worse, the socket
    then closed, so the client never received ``hello_ok`` and sat in front of
    empty regelset and puntentelling dropdowns with no idea why.
    """
    import json

    import websockets

    async with websockets.connect(server) as socket:
        await socket.send(
            json.dumps({"v": PROTOCOL_VERSION, "msg": {"type": "hello", "username": "J"}})
        )
        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))["msg"]

    assert message["type"] == "error"
    assert message["code"] == "username_invalid"
    assert "2 tot 20" in message["text"]


async def test_an_accented_name_is_welcome(server: str) -> None:
    """The rules are about characters that break renderers, not about being Dutch."""
    import json

    import websockets

    async with websockets.connect(server) as socket:
        await socket.send(
            json.dumps({"v": PROTOCOL_VERSION, "msg": {"type": "hello", "username": "José"}})
        )
        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))["msg"]

    assert message["type"] == "hello_ok"
    assert message["username"] == "José"
    # The point of getting this far: this is what fills the two dropdowns.
    assert message["rulesets"] and message["scorings"]


async def test_a_second_client_cannot_steal_a_live_username(server: str) -> None:
    clients = await seat_four(server)
    try:
        impostor = ScriptedClient(server, "Jan")
        import websockets

        impostor.socket = await websockets.connect(server)
        await impostor.send("hello", username="Jan")
        message = await impostor._recv(timeout=10)
        assert message["type"] == "error"
        assert message["code"] == "username_taken"
        await impostor.close()

        # The real Jan is undisturbed.
        await clients[0].send("chat_send", text="ik ben er nog")
        await clients[0].wait_for("chat", predicate=lambda m: m.get("sender") == "Jan", timeout=10)
    finally:
        for client in clients:
            await client.close()


async def test_a_dead_session_can_be_rebound_without_a_token(server: str) -> None:
    """Username alone is enough when the old connection is gone."""
    clients = await seat_four(server)
    try:
        await play_a_few_tricks(clients, count=1)
        korneel = clients[3]
        await korneel.close()
        await clients[0].wait_for("game_paused", timeout=15)
        await asyncio.sleep(0.2)

        back = ScriptedClient(server, "Korneel")
        import websockets

        back.socket = await websockets.connect(server)
        # No resume_token at all - the requirement says the username binds.
        await back.send("hello", username="Korneel")
        hello = await back.wait_for("hello_ok", timeout=10)
        assert hello["username"] == "Korneel"
        assert hello["current_lobby"] is not None
        snapshot = await back.wait_for("snapshot", timeout=15)
        assert snapshot["snapshot"]["your_seat"] == 3
        assert len(snapshot["snapshot"]["your_hand"]) > 0
        await back.close()
    finally:
        for client in clients:
            await client.close()
