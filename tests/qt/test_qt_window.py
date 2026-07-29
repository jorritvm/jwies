"""Build the real window offscreen and render a real snapshot into it.

Catches the whole class of failures that unit-testing the reducer cannot: a
missing asset, a bad SVG element id, a signal wired to a method that does not
exist, a layout that throws on construction.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")

from jwies_qt_client.main_window import MainWindow
from jwies_qt_client.settings import ClientSettings
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def application() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(application: QApplication, tmp_path) -> MainWindow:
    settings = ClientSettings(username="Jan")
    settings.save(tmp_path / "player.yaml")
    return MainWindow(settings)


SNAPSHOT = {
    "type": "snapshot",
    "snapshot": {
        "lobby": {
            "id": "l1",
            "name": "Testtafel",
            "host": "Jan",
            "ruleset": "klassiek",
            "scoring": "schaal_a",
            "status": "running",
            "members": [],
        },
        "phase": "playing",
        "round_number": 1,
        "multiplier": "1",
        "your_seat": 0,
        "dealer_seat": 3,
        "seats": [
            {
                "seat": 0,
                "username": "Jan",
                "connected": True,
                "is_dealer": False,
                "is_declarer": True,
                "total": "0",
            },
            {
                "seat": 1,
                "username": "Piet",
                "connected": True,
                "is_dealer": False,
                "is_declarer": False,
                "total": "0",
            },
            {
                "seat": 2,
                "username": "Joris",
                "connected": False,
                "is_dealer": False,
                "is_declarer": False,
                "total": "0",
            },
            {
                "seat": 3,
                "username": "Korneel",
                "connected": True,
                "is_dealer": True,
                "is_declarer": False,
                "total": "0",
            },
        ],
        "your_hand": ["AH", "KD", "10S", "2C", "QH"],
        "open_hands": {},
        "turned_trump": None,
        "trump": "H",
        "bids": [],
        "contract": {
            "key": "alone",
            "name": "alleen gaan",
            "tricks_required": 5,
            "declarers": [0],
            "defenders": [1, 2, 3],
            "trump": "H",
            "open_hand": False,
        },
        "current_trick": [{"seat": 3, "card": "3H"}],
        "last_trick": None,
        "trick_counts": {"declarers": 2, "defenders": 1},
        "totals": {"Jan": "0"},
        "pending_seat": 0,
        "prompt": {
            "kind": "play",
            "bid_options": [],
            "legal_cards": ["AH", "QH"],
            "cut_minimum": 0,
            "cut_maximum": 0,
        },
        "paused": False,
        "missing_players": [],
    },
}


def test_the_window_builds(window: MainWindow) -> None:
    assert window.windowTitle().startswith("jwies")


def test_a_snapshot_renders_without_error(window: MainWindow) -> None:
    window.on_message(SNAPSHOT)
    assert window.state["your_seat"] == 0
    assert window.state["hand"] == ["AH", "KD", "10S", "2C", "QH"]
    assert len(window.scene.own_hand) == 5


def test_only_the_legal_cards_are_clickable(window: MainWindow) -> None:
    window.on_message(SNAPSHOT)
    playable = {card.code for card in window.scene.own_hand if card.is_playable}
    assert playable == {"AH", "QH"}


def test_the_trick_counter_shows_dutch(window: MainWindow) -> None:
    window.on_message(SNAPSHOT)
    text = window.scene.trick_counter.toPlainText()
    assert "Aanval: 2" in text
    assert "Verdediging: 1" in text
    assert "harten" in text


def test_bid_buttons_come_from_the_server_prompt(window: MainWindow) -> None:
    message = {
        "type": "prompt",
        "prompt": {
            "kind": "bid",
            "bid_options": [
                {"type": "pass", "tricks": None, "suit": None},
                {"type": "abondance", "tricks": 10, "suit": None},
            ],
            "legal_cards": [],
            "cut_minimum": 0,
            "cut_maximum": 0,
        },
    }
    window.on_message(SNAPSHOT)
    window.on_message(message)
    labels = [
        window.bid_layout.itemAt(index).widget().text()
        for index in range(window.bid_layout.count())
    ]
    assert labels == ["Passen", "Abondance 10"]


def test_a_paused_game_disables_playing(window: MainWindow) -> None:
    window.on_message(SNAPSHOT)
    window.on_message({"type": "game_paused", "missing": ["Joris"], "text": "Joris is weg."})
    assert window.state["paused"] is True
    assert window.play_button.isEnabled() is False


def test_chat_text_from_the_server_is_shown_as_is(window: MainWindow) -> None:
    window.on_message(
        {
            "type": "chat",
            "kind": "server",
            "text": "Jan wint de slag.",
            "sender": None,
            "private": False,
        }
    )
    assert "Jan wint de slag." in window.chat_log.toPlainText()


def test_the_lobby_list_renders(window: MainWindow) -> None:
    window.on_message(
        {
            "type": "lobby_list",
            "lobbies": [
                {
                    "id": "l1",
                    "name": "Testtafel",
                    "ruleset": "klassiek",
                    "scoring": "schaal_a",
                    "status": "waiting",
                    "players": 2,
                    "seats_free": 2,
                }
            ],
        }
    )
    assert window.lobby_list.count() == 1
    assert "Testtafel" in window.lobby_list.item(0).text()
    assert "wacht op spelers" in window.lobby_list.item(0).text()
