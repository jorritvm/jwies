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

from jwies_qt_client.main_window import CHAT_MINIMUM_WIDTH, MainWindow
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
            },
            {
                "seat": 1,
                "username": "Piet",
                "connected": True,
                "is_dealer": False,
            },
            {
                "seat": 2,
                "username": "Joris",
                "connected": False,
                "is_dealer": False,
            },
            {
                "seat": 3,
                "username": "Korneel",
                "connected": True,
                "is_dealer": True,
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
            "trump": "H",
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


class TestFolding:
    """Stopping a lost round early is offered as a button, never as a dialog.

    A round nobody can win any more is the worst possible moment to interrupt
    the table with a modal, so this one deliberately does not go through
    ``react_to_prompt``. It is drawn from the snapshot like everything else.
    """

    def test_it_is_hidden_until_the_server_offers_it(self, window: MainWindow) -> None:
        window.on_message(SNAPSHOT)
        assert window.fold_button.isHidden()

    def test_it_appears_with_the_tally(self, window: MainWindow) -> None:
        window.show()
        window.on_message(snapshot(folding_offered=True, folded=[1, 3]))
        assert window.fold_button.isVisible()
        assert "2/4" in window.fold_button.text()

    def test_it_shows_whether_you_agreed(self, window: MainWindow) -> None:
        window.on_message(snapshot(folding_offered=True, folded=[1, 3]))
        assert not window.fold_button.isChecked(), "stoel 0 heeft niet opgegeven"
        window.on_message(snapshot(folding_offered=True, folded=[0, 1, 3]))
        assert window.fold_button.isChecked()

    def test_the_server_has_the_last_word(self, window: MainWindow) -> None:
        """A click is a request, not a decision - the snapshot corrects it."""
        window.on_message(snapshot(folding_offered=True, folded=[]))
        window.fold_button.setChecked(True)
        window.on_message(snapshot(folding_offered=True, folded=[]))
        assert not window.fold_button.isChecked()

    def test_it_disappears_again_when_the_offer_lapses(self, window: MainWindow) -> None:
        window.show()
        window.on_message(snapshot(folding_offered=True, folded=[0]))
        assert window.fold_button.isVisible()
        window.on_message(snapshot(folding_offered=False, folded=[]))
        assert window.fold_button.isHidden()
        assert not window.fold_button.isChecked()

    def test_offering_it_opens_no_dialog(
        self, window: MainWindow, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[str] = []

        def refuse_to_be_opened(*_args: object, **_kwargs: object) -> tuple[int, bool]:
            opened.append("dialog")
            return 0, False

        monkeypatch.setattr(QMessageBox, "question", staticmethod(refuse_to_be_opened))
        monkeypatch.setattr(QInputDialog, "getInt", staticmethod(refuse_to_be_opened))
        window.on_message(snapshot(folding_offered=True, folded=[0, 1, 2]))
        window.refresh_table()
        assert opened == []


class TestErrorsOnTheLobbyPage:
    """A refusal has to be visible on the page you are looking at.

    Errors went only to the chat log, which lives on the table page - so being
    refused a new table looked exactly like the button doing nothing, and the
    obvious conclusion was that the server could only host one game.
    """

    def test_a_refusal_is_shown_on_the_lobby_page(self, window: MainWindow) -> None:
        window.on_message(
            {"type": "error", "code": "lobby_exists", "text": "Er is al een lobby met die naam."}
        )
        assert window.lobby_page.error_label.isVisible() or not window.lobby_page.isVisible()
        assert "al een lobby" in window.lobby_page.error_label.text()

    def test_a_fresh_listing_clears_it(self, window: MainWindow) -> None:
        window.on_message({"type": "error", "code": "lobby_exists", "text": "Bezet."})
        window.on_message({"type": "lobby_list", "lobbies": []})
        assert window.lobby_page.error_label.isHidden()

    def test_at_the_table_it_still_goes_to_the_chat(self, window: MainWindow) -> None:
        window.on_message(SNAPSHOT)  # switches to the table page
        window.on_message({"type": "error", "code": "illegal_move", "text": "Mag niet."})
        assert "Mag niet." in window.chat_log.toPlainText()
        assert window.lobby_page.error_label.text() == ""

    def test_the_suggested_table_name_is_your_own(self, window: MainWindow) -> None:
        """Everybody starting from the same name is what caused the clash."""
        window.on_message(
            {"type": "hello_ok", "username": "Korneel", "resume_token": "t",
             "current_lobby": None, "rulesets": [], "scorings": []}
        )
        assert window.lobby_page.new_name.text() == "Tafel van Korneel"

    def test_a_name_you_typed_yourself_is_left_alone(self, window: MainWindow) -> None:
        window.lobby_page.new_name.setText("De Kaartclub")
        window.on_message(
            {"type": "hello_ok", "username": "Korneel", "resume_token": "t",
             "current_lobby": None, "rulesets": [], "scorings": []}
        )
        assert window.lobby_page.new_name.text() == "De Kaartclub"


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


def test_your_hand_is_never_drawn_faded(window: MainWindow) -> None:
    """Your cards look the same at every stage of the round.

    The illegal ones used to be drawn at 55% opacity while it was your turn,
    which made the whole hand look greyed out at exactly the moment you were
    being asked to act. Legality decides what you can click, not how it looks.
    """
    window.on_message(SNAPSHOT)  # a `play` prompt where only AH and QH are legal
    assert window.state["prompt"]["kind"] == "play"
    faded = {card.code: card.opacity() for card in window.scene.own_hand if card.opacity() < 1.0}
    assert not faded, f"deze kaarten zijn doorschijnend: {faded}"


class TestTheChatIsUsable:
    """The chat pane opens wide enough to read, and the split can be dragged.

    It used to open at about 100px: a splitter divides space by size hint before
    the stretch factors get a say, and the graphics view's hint is large. The
    handle was 4px, which between a green table and a white box reads as no
    handle at all.
    """

    def test_it_opens_wide_enough_to_read(self, window: MainWindow) -> None:
        window.show()
        table, chat = window.splitter.sizes()
        assert chat >= CHAT_MINIMUM_WIDTH, f"chat opent op {chat}px"
        assert table > chat, "de tafel hoort nog altijd het grootste deel te krijgen"

    def test_the_handle_can_be_grabbed(self, window: MainWindow) -> None:
        assert window.splitter.handleWidth() >= 6

    def test_the_split_is_set_explicitly(self, window: MainWindow) -> None:
        """Left to its own devices the splitter gave the chat about 9%.

        A share is asserted rather than a pixel count: the offscreen platform
        decides how wide the window really is, and at any width the chat should
        get a usable fraction of it.
        """
        window.show()
        table, chat = window.splitter.sizes()
        share = chat / (table + chat)
        assert share > 0.2, f"chat krijgt maar {share:.0%} van de breedte"

    def test_neither_side_can_be_collapsed_away(self, window: MainWindow) -> None:
        window.show()
        window.splitter.setSizes([2000, 0])
        assert min(window.splitter.sizes()) > 0


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
