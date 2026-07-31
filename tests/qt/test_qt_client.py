"""PyQt client: the parts that can be tested without a display.

Seat mapping, card-id translation and the state reducer carry all the logic the
client still has, so they are the parts worth testing. The widgets themselves
need a running X server / desktop session and are exercised by hand.
"""

from __future__ import annotations

import pytest
from jwies_core.cards import full_deck
from jwies_qt_client.cards import CARD_BACK, card_label, suit_label, svg_element_id
from jwies_qt_client.layout import DIRECTIONS, direction_of
from jwies_qt_client.settings import ClientSettings
from jwies_qt_client.state import ClientState


class TestSeatMapping:
    def test_you_are_always_south(self) -> None:
        for seat in range(4):
            assert direction_of(seat, seat) == "SOUTH"

    def test_the_others_go_round_clockwise(self) -> None:
        # Replaces the old SEATWEST/SEATNORTH/SEATEAST messages entirely.
        assert direction_of(1, 0) == "WEST"
        assert direction_of(2, 0) == "NORTH"
        assert direction_of(3, 0) == "EAST"

    def test_it_wraps(self) -> None:
        assert direction_of(0, 3) == "WEST"
        assert direction_of(1, 3) == "NORTH"
        assert direction_of(2, 3) == "EAST"

    def test_every_seat_gets_a_distinct_direction(self) -> None:
        for your_seat in range(4):
            seen = {direction_of(seat, your_seat) for seat in range(4)}
            assert seen == set(DIRECTIONS)

    def test_it_copes_with_not_being_seated_yet(self) -> None:
        assert direction_of(2, None) == "SOUTH"


class TestCardTranslation:
    @pytest.mark.parametrize("card", full_deck())
    def test_it_agrees_with_the_engine(self, card) -> None:
        # The client has its own table so it needs no rules engine; this test
        # is what stops the two from drifting apart.
        assert svg_element_id(card.code) == card.svg_element_id

    def test_the_back_passes_through(self) -> None:
        assert svg_element_id(CARD_BACK) == CARD_BACK

    def test_dutch_card_labels(self) -> None:
        assert card_label("AH") == "harten aas"
        assert card_label("10S") == "schoppen tien"
        assert card_label(CARD_BACK) == "gedekte kaart"

    def test_dutch_suit_labels(self) -> None:
        assert suit_label("C") == "klaveren"
        assert suit_label(None) == "zonder troef"


class TestStateReducer:
    def test_a_snapshot_replaces_everything(self) -> None:
        state = ClientState()
        state.apply_message(
            {
                "type": "snapshot",
                "snapshot": {
                    "lobby": {"id": "l1"},
                    "your_seat": 2,
                    "dealer_seat": 1,
                    "your_hand": ["AH", "KD"],
                    "current_trick": [{"seat": 1, "card": "2C"}],
                    "trick_counts": {"declarers": 3, "defenders": 4},
                    "paused": False,
                },
            }
        )
        assert state["your_seat"] == 2
        assert state["hand"] == ["AH", "KD"]
        assert state["trick_counts"]["declarers"] == 3
        assert state["in_game"] is True

    def test_playing_your_own_card_removes_it_from_your_hand(self) -> None:
        state = ClientState()
        state.update(your_seat=0, hand=["AH", "KD"])
        state.apply_message(
            {"type": "card_played", "seat": 0, "card": "AH", "position_in_trick": 1}
        )
        assert state["hand"] == ["KD"]
        assert state["trick"] == [{"seat": 0, "card": "AH"}]

    def test_another_players_card_leaves_your_hand_alone(self) -> None:
        state = ClientState()
        state.update(your_seat=0, hand=["AH", "KD"])
        state.apply_message(
            {"type": "card_played", "seat": 1, "card": "2C", "position_in_trick": 1}
        )
        assert state["hand"] == ["AH", "KD"]

    def test_the_table_is_swept_after_a_trick(self) -> None:
        state = ClientState()
        state.update(trick=[{"seat": 0, "card": "AH"}])
        state.apply_message(
            {
                "type": "trick_completed",
                "winner_seat": 0,
                "cards": [{"seat": 0, "card": "AH"}],
                "trick_counts": {"declarers": 1, "defenders": 0},
                "text": "Jan wint de slag.",
            }
        )
        assert state["last_trick"] == [{"seat": 0, "card": "AH"}]
        state.apply_message({"type": "table_cleared"})
        assert state["trick"] == []

    def test_pause_and_resume(self) -> None:
        state = ClientState()
        state.apply_message({"type": "game_paused", "missing": ["Korneel"], "text": "..."})
        assert state["paused"] is True
        assert state["missing"] == ["Korneel"]
        assert state["prompt"] is None
        state.apply_message({"type": "game_resumed", "text": "..."})
        assert state["paused"] is False
        assert state["missing"] == []

    def test_a_new_round_clears_the_previous_contract(self) -> None:
        state = ClientState()
        state.update(contract={"key": "misere"}, trump="H", turned_trump="AH")
        state.apply_message(
            {"type": "round_started", "round_number": 2, "dealer_seat": 1, "multiplier": "1"}
        )
        assert state["contract"] is None
        assert state["trump"] is None
        assert state["turned_trump"] is None
        assert state["round_number"] == 2

    def test_the_prompt_carries_the_legal_cards(self) -> None:
        state = ClientState()
        state.apply_message(
            {
                "type": "prompt",
                "prompt": {
                    "kind": "play",
                    "legal_cards": ["AH", "KH"],
                    "bid_options": [],
                    "cut_minimum": 0,
                    "cut_maximum": 0,
                },
            }
        )
        # The client never works out follow-suit itself.
        assert state["prompt"]["legal_cards"] == ["AH", "KH"]


class TestSettings:
    def test_missing_file_gives_defaults(self, tmp_path) -> None:
        settings = ClientSettings.load(tmp_path / "nope.yaml")
        assert settings.username == ""
        assert settings.server_url.startswith("ws://")

    def test_round_trip(self, tmp_path) -> None:
        path = tmp_path / "player.yaml"
        ClientSettings(username="Jan", resume_token="abc").save(path)
        loaded = ClientSettings.load(path)
        assert loaded.username == "Jan"
        assert loaded.resume_token == "abc"

    def test_a_corrupt_file_does_not_crash_the_client(self, tmp_path) -> None:
        path = tmp_path / "player.yaml"
        path.write_text("dit is: [geen geldige yaml", encoding="utf-8")
        assert ClientSettings.load(path).username == ""


def test_bid_labels_are_dutch() -> None:
    from jwies_qt_client.main_window import bid_label

    assert bid_label({"type": "pass"}) == "Passen"
    assert bid_label({"type": "abondance", "tricks": 10}) == "Abondance 10"
    assert bid_label({"type": "misere_ouverte"}) == "Miserie bloot"


def test_the_client_declares_no_dependency_on_the_engine() -> None:
    """jwies-qt-client must not pull in jwies-core."""
    import tomllib
    from pathlib import Path

    manifest = Path(__file__).resolve().parents[2] / "packages" / "jwies-qt-client" / "pyproject.toml"
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    dependencies = " ".join(data["project"]["dependencies"])
    assert "jwies-core" not in dependencies
    assert "fastapi" not in dependencies
    assert "uvicorn" not in dependencies
