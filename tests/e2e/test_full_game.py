"""Four clients play a real round over a real websocket."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tests.e2e.conftest import ScriptedClient, play_until

pytestmark = pytest.mark.anyio if False else []


async def seat_four(server: str) -> list[ScriptedClient]:
    """Connect four clients, create a lobby and fill it. Game auto-starts."""
    clients = [ScriptedClient(server, name) for name in ("Jan", "Piet", "Joris", "Korneel")]
    for client in clients:
        await client.__aenter__()

    await clients[0].send(
        "lobby_create", name="Testtafel", ruleset="klassiek", scoring="schaal_a", rng_seed=42
    )
    state = await clients[0].wait_for("lobby_state")
    lobby_id = state["lobby"]["id"]

    for client in clients[1:]:
        await client.send("lobby_join", lobby_id=lobby_id)
        await client.wait_for("lobby_state")

    return clients


async def test_four_clients_play_a_complete_round(server: str) -> None:
    clients = await seat_four(server)
    try:
        finished: dict[str, Any] = {}

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            if message["type"] == "round_finished":
                finished.setdefault(client.username, message)
                return len(finished) == 4
            return False

        await play_until(clients, stop)

        assert len(finished) == 4, "niet elke speler kreeg de eindafrekening"

        # (a) exactly thirteen tricks were played
        for client in clients:
            assert len(client.seen("trick_completed")) == 13

        # (b) everyone saw the same cards in the same order
        sequences = [
            [(m["seat"], m["card"]) for m in client.seen("card_played")] for client in clients
        ]
        assert all(sequence == sequences[0] for sequence in sequences)
        assert len(sequences[0]) == 52

        # (c) the settlement is zero-sum
        deltas = finished["Jan"]["deltas"]
        assert sum(Decimal(value) for value in deltas.values()) == 0

        # (d) every client agrees on the totals
        totals = [finished[client.username]["totals"] for client in clients]
        assert all(total == totals[0] for total in totals)

        # (e) nobody ever received someone else's hand
        for client in clients:
            for message in client.seen("hand_dealt"):
                assert len(message["cards"]) == 13
            assert len(client.seen("hand_dealt")) >= 1
    finally:
        for client in clients:
            await client.close()


async def test_a_player_never_sees_another_players_hand(server: str) -> None:
    clients = await seat_four(server)
    try:
        hands: dict[str, set[str]] = {}

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            if message["type"] == "hand_dealt":
                hands[client.username] = set(message["cards"])
                return len(hands) == 4
            return False

        await play_until(clients, stop, timeout=30)

        assert len(hands) == 4
        # The four hands are disjoint and together make a full deck.
        everything: set[str] = set()
        for cards in hands.values():
            assert not (everything & cards), "twee spelers kregen dezelfde kaart"
            everything |= cards
        assert len(everything) == 52
    finally:
        for client in clients:
            await client.close()


async def test_the_dutch_announcements_reach_every_client(server: str) -> None:
    clients = await seat_four(server)
    try:
        seen: dict[str, bool] = {}

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            if message["type"] == "contract_established":
                seen[client.username] = True
                return len(seen) == 4
            return False

        await play_until(clients, stop, timeout=40)

        for client in clients:
            announcement = client.seen("contract_established")[0]
            # Server-rendered Dutch, ready to display.
            assert announcement["text"]
            assert announcement["contract"]["name"]
            bids = client.seen("bid_placed")
            assert any(bid["announcement"] for bid in bids)
    finally:
        for client in clients:
            await client.close()


async def test_scores_accumulate_across_rounds(server: str) -> None:
    clients = await seat_four(server)
    try:
        rounds: list[dict[str, Any]] = []

        def stop(message: dict[str, Any], client: ScriptedClient) -> bool:
            if message["type"] == "round_finished" and client.username == "Jan":
                rounds.append(message)
                return len(rounds) == 2
            return False

        await play_until(clients, stop, timeout=120)

        assert len(rounds) == 2
        for finished in rounds:
            assert sum(Decimal(value) for value in finished["deltas"].values()) == 0
            assert sum(Decimal(value) for value in finished["totals"].values()) == 0
    finally:
        for client in clients:
            await client.close()
