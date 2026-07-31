"""Build the real window offscreen and render a real snapshot into it.

Catches the whole class of failures that unit-testing the reducer cannot: a
missing asset, a bad SVG element id, a signal wired to a method that does not
exist, a layout that throws on construction.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6.QtWidgets")

from jwies_qt_client.main_window import MainWindow
from jwies_qt_client.settings import ClientSettings
from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox


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


def prompt(kind: str, **fields: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "bid_options": [],
        "legal_cards": [],
        "cut_minimum": 0,
        "cut_maximum": 0,
        **fields,
    }


def snapshot(**overrides: Any) -> dict[str, Any]:
    """The table above with a few fields swapped out.

    Everything the client believes now arrives this way: the server sends a
    fresh snapshot after every change, and nothing else carries state.
    """
    return {"type": "snapshot", "snapshot": {**SNAPSHOT["snapshot"], **overrides}}


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
    window.on_message(SNAPSHOT)
    window.on_message(
        snapshot(
            prompt=prompt(
                "bid",
                bid_options=[
                    {"type": "pass", "tricks": None, "suit": None},
                    {"type": "abondance", "tricks": 10, "suit": None},
                ],
            )
        )
    )
    labels = [
        window.bid_layout.itemAt(index).widget().text()
        for index in range(window.bid_layout.count())
    ]
    assert labels == ["Passen", "Abondance 10"]


def test_a_paused_game_disables_playing(window: MainWindow) -> None:
    window.on_message(SNAPSHOT)
    window.on_message({"type": "game_paused", "missing": ["Joris"], "text": "Joris is weg."})
    window.on_message(snapshot(paused=True, missing_players=["Joris"]))
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


class TestPromptsThatAskAQuestion:
    """Opening a modal is a reaction to a new prompt, never part of drawing.

    A modal spins a nested Qt event loop, so the socket keeps delivering while
    one is open. If the render path opened them, every chat line arriving after
    the shuffle prompt would stack another dialog on top.
    """

    @pytest.fixture
    def asked(self, window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """Record every dialog opened and every answer sent."""
        opened: list[str] = []

        def question(*_args: object, **_kwargs: object) -> object:
            opened.append("shuffle")
            return QMessageBox.StandardButton.Yes

        def get_int(*_args: object, **_kwargs: object) -> tuple[int, bool]:
            opened.append("cut")
            return 7, True

        monkeypatch.setattr(QMessageBox, "question", staticmethod(question))
        monkeypatch.setattr(QInputDialog, "getInt", staticmethod(get_int))
        monkeypatch.setattr(window.connection, "send", lambda *a, **k: None)
        return opened

    def test_a_shuffle_prompt_asks_once(self, window: MainWindow, asked: list[str]) -> None:
        window.on_message(snapshot(prompt=prompt("shuffle")))
        assert asked == ["shuffle"]

    def test_later_snapshots_do_not_ask_again(self, window: MainWindow, asked: list[str]) -> None:
        # The exact stacking bug: the server keeps sending snapshots that still
        # carry the shuffle prompt until the dealer's answer arrives, and the
        # socket keeps delivering while the first dialog holds a nested loop.
        window.on_message(snapshot(prompt=prompt("shuffle")))
        for _ in range(3):
            window.on_message(
                {"type": "chat", "kind": "server", "text": "Jan schudt.", "sender": None}
            )
            window.on_message(snapshot(prompt=prompt("shuffle")))
        assert asked == ["shuffle"]

    def test_redrawing_the_table_never_asks(self, window: MainWindow, asked: list[str]) -> None:
        window.on_message(snapshot(prompt=prompt("shuffle")))
        asked.clear()
        window.refresh_table()
        window.on_last_trick_toggled(True)
        assert asked == []

    def test_a_cut_prompt_asks_for_a_number(self, window: MainWindow, asked: list[str]) -> None:
        window.on_message(snapshot(prompt=prompt("cut", cut_minimum=1, cut_maximum=51)))
        assert asked == ["cut"]

    def test_a_bid_prompt_asks_nothing(self, window: MainWindow, asked: list[str]) -> None:
        # Bidding is answered with the buttons on the table, not with a dialog.
        window.on_message(
            snapshot(
                prompt=prompt("bid", bid_options=[{"type": "pass", "tricks": None, "suit": None}])
            )
        )
        assert asked == []

    def test_a_resumed_game_asks_again(self, window: MainWindow, asked: list[str]) -> None:
        # The server re-offers the pending turn after a pause, because it never
        # recorded having asked. The client must accept that offer.
        window.on_message(snapshot(prompt=prompt("shuffle")))
        window.on_message(snapshot(prompt=prompt("shuffle"), paused=True, missing_players=["Jo"]))
        window.on_message(snapshot(prompt=prompt("shuffle")))
        assert asked == ["shuffle", "shuffle"]


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
    listing = window.lobby_page.lobby_list
    assert listing.count() == 1
    assert "Testtafel" in listing.item(0).text()
    assert "wacht op spelers" in listing.item(0).text()
