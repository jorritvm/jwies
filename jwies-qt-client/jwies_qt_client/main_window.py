"""The main window: the card table, and the router for incoming messages.

The window enables the buttons the server's snapshot names and draws the
state the server sends.
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from jwies_qt_client import ASSETS
from jwies_qt_client.lobby_page import ConnectDialog, LobbyPage
from jwies_qt_client.net import ServerConnection
from jwies_qt_client.settings import ClientSettings
from jwies_qt_client.state import ClientState
from jwies_qt_client.table_scene import TableScene
from jwies_qt_client.widgets import CardSignals, ChooseSuitDialog, TableGraphicsView

__all__ = ["MainWindow", "bid_label"]

log = logging.getLogger(__name__)

BID_LABELS = {
    "pass": "Passen",
    "ask": "Vragen",
    "join": "Meegaan",
    "alone": "Alleen gaan",
    "abondance": "Abondance",
    "misere": "Miserie",
    "misere_ouverte": "Miserie bloot",
    "troel": "Troel",
    "solo": "Solo",
    "solo_slim": "Solo slim",
    "pico": "Pico",
}

SUIT_CHOOSING_BIDS = {"ask", "abondance", "solo"}

# Enough for a wrapped chat line plus the scrollbar. Also the width the chat
# opens at, three times over for the table beside it.
CHAT_MINIMUM_WIDTH = 260


def bid_label(bid: dict[str, Any]) -> str:
    """Dutch label for a bid option offered by the server."""
    text = BID_LABELS.get(bid["type"], bid["type"])
    if bid.get("tricks") is not None and bid["type"] in ("abondance", "alone"):
        text = f"{text} {bid['tricks']}"
    return text


class MainWindow(QMainWindow):
    def __init__(self, settings: ClientSettings) -> None:
        super().__init__()
        self.settings = settings
        self.state = ClientState()
        self.connection = ServerConnection(self)
        self.card_signals = CardSignals()

        self.setWindowTitle("jwies - Vlaamse wies")
        self.setWindowIcon(QIcon(str(ASSETS / "playing-card.png")))
        self.resize(1100, 720)

        self.renderer = QSvgRenderer(str(ASSETS / "svg-cards.svg"))

        self._build_ui()
        self._wire()

    # --- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        self.lobby_page = LobbyPage()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.lobby_page)
        self.stack.addWidget(self._build_table_page())
        self.setCentralWidget(self.stack)

        menu = self.menuBar().addMenu("&Spel")
        connect_action = QAction("&Verbinden...", self)
        connect_action.triggered.connect(self.ask_to_connect)
        menu.addAction(connect_action)
        leave_action = QAction("Tafel &verlaten", self)
        leave_action.triggered.connect(self.leave_table)
        menu.addAction(leave_action)

        self.statusBar().showMessage("Niet verbonden")

    def _build_table_page(self) -> QWidget:
        self.scene = TableScene(self.renderer, self.card_signals)
        self.view = TableGraphicsView(self.scene.field)
        self.view.setScene(self.scene)
        self.view.setRenderHints(self.view.renderHints())

        # Buttons on the right of the table.
        self.bid_holder = QWidget()
        self.bid_layout = QVBoxLayout(self.bid_holder)
        self.bid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.play_button = QPushButton("Speel kaart")
        self.play_button.setEnabled(False)
        self.last_trick_button = QPushButton("Toon laatste slag")
        self.last_trick_button.setCheckable(True)
        # Deliberately a button and not a dialog: a round nobody can win any
        # more is exactly the wrong moment to interrupt the table with a modal.
        # It sits there quietly and is hidden whenever folding is not on offer.
        self.fold_button = QPushButton("Ronde opgeven")
        self.fold_button.setCheckable(True)
        self.fold_button.hide()

        buttons = QWidget()
        button_layout = QVBoxLayout(buttons)
        button_layout.addWidget(self.bid_holder, 1)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.fold_button)
        button_layout.addWidget(self.last_trick_button)

        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.addWidget(self.view, 1)
        left_layout.addWidget(buttons)

        self.chat_log = QPlainTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Typ een bericht of !help")
        chat = QWidget()
        chat_layout = QVBoxLayout(chat)
        chat_layout.addWidget(self.chat_log, 1)
        chat_layout.addWidget(self.chat_input)
        # Without this the chat is squeezed to a sliver: the graphics view's
        # size hint is large, and a splitter divides space by hint before the
        # stretch factors get a say.
        chat.setMinimumWidth(CHAT_MINIMUM_WIDTH)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(left)
        self.splitter.addWidget(chat)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        # The default 4px handle is nearly invisible between a green table and a
        # white chat box, which makes the split look fixed when it is not.
        self.splitter.setHandleWidth(8)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([CHAT_MINIMUM_WIDTH * 3, CHAT_MINIMUM_WIDTH])

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(self.splitter)
        return page

    def _wire(self) -> None:
        self.connection.message_received.connect(self.on_message)
        self.connection.connected.connect(lambda: self.statusBar().showMessage("Verbonden"))
        self.connection.disconnected.connect(
            lambda: self.statusBar().showMessage("Verbinding verbroken, opnieuw proberen...")
        )
        self.connection.connection_error.connect(
            lambda text: self.statusBar().showMessage(f"Netwerkfout: {text}")
        )

        self.card_signals.selected.connect(self.on_card_selected)
        self.play_button.clicked.connect(self.on_play_clicked)
        self.fold_button.clicked.connect(
            lambda checked: self.connection.send("fold", fold=checked)
        )
        self.last_trick_button.toggled.connect(self.on_last_trick_toggled)
        self.chat_input.returnPressed.connect(self.on_chat_entered)

        page = self.lobby_page
        page.join_requested.connect(
            lambda lobby_id: self.connection.send("lobby_join", lobby_id=lobby_id)
        )
        page.delete_requested.connect(
            lambda lobby_id: self.connection.send("lobby_delete", lobby_id=lobby_id)
        )
        page.refresh_requested.connect(lambda: self.connection.send("lobby_list"))
        page.create_requested.connect(
            lambda name, ruleset, scoring: self.connection.send(
                "lobby_create", name=name, ruleset=ruleset or None, scoring=scoring or None
            )
        )

    # --- connecting --------------------------------------------------------

    def ask_to_connect(self) -> None:
        dialog = ConnectDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        username = dialog.name_field.text().strip()
        url = dialog.url_field.text().strip()
        if not username:
            QMessageBox.warning(self, "jwies", "Vul een naam in.")
            return
        self.settings.username = username
        self.settings.server_url = url
        self.settings.save()
        self.statusBar().showMessage("Verbinden...")
        self.connection.connect_to(url, username, self.settings.resume_token)

    def leave_table(self) -> None:
        """Get up from the table and go back to the list.

        The switch happens here rather than on a reply, because the moment the
        server takes you off the member list you stop receiving anything that
        lobby sends - so waiting for confirmation means waiting forever. The
        server cannot refuse a leave, so acting on it immediately is safe; the
        lobby listing it sends back then fills the page.
        """
        self.connection.send("lobby_leave")
        self.state.update(
            in_game=False,
            prompt=None,
            hand=[],
            trick=[],
            last_trick=None,
            contract=None,
            seats=[],
            folding_offered=False,
            folded=[],
        )
        self._selected_card = None
        self._prompt_shown = None
        self.stack.setCurrentIndex(0)
        self.statusBar().showMessage("Je hebt de tafel verlaten.")

    def autoconnect(self) -> None:
        if self.settings.username:
            self.connection.connect_to(
                self.settings.server_url, self.settings.username, self.settings.resume_token
            )
        else:
            self.ask_to_connect()

    # --- incoming ----------------------------------------------------------

    def on_message(self, message: dict[str, Any]) -> None:
        self.state.apply_message(message)
        kind = message.get("type")

        if kind == "hello_ok":
            self.settings.resume_token = message.get("resume_token")
            self.settings.save()
            self.lobby_page.set_options(
                message.get("rulesets") or [], message.get("scorings") or []
            )
            self.lobby_page.suggest_a_table_name(str(message.get("username") or ""))
            self.statusBar().showMessage(f"Verbonden als {message.get('username')}")
            if not message.get("current_lobby"):
                self.connection.send("lobby_list")
        elif kind == "chat":
            self.append_chat(message)
        elif kind == "error":
            self.append_chat({"text": message["text"], "kind": "system"})
            if message["code"] in ("username_taken", "username_invalid"):
                QMessageBox.warning(self, "jwies", message["text"])
            elif self.stack.currentIndex() == 0:
                # The chat log is on the table page, so on the lobby page that
                # append above is written into thin air.
                self.lobby_page.show_error(message["text"])
        elif kind == "lobby_list":
            self.lobby_page.show_lobbies(self.state.get("lobbies", []))
        elif kind in ("player_joined", "player_left", "player_disconnected", "player_reconnected"):
            self.connection.send("lobby_list")

        if kind in ("game_started", "snapshot"):
            self.stack.setCurrentIndex(1)
        if self.state.get("in_game"):
            self.refresh_table()

        # Asking a question is a reaction to news, not part of drawing. It goes
        # last because a modal spins a nested event loop: the table must already
        # be drawn and consistent before one opens, and further messages will
        # arrive while it is up.
        self.react_to_prompt(self.state.get("prompt"))

    def append_chat(self, message: dict[str, Any]) -> None:
        sender = message.get("sender")
        text = message["text"]
        self.chat_log.appendPlainText(f"{sender}: {text}" if sender else text)

    def refresh_table(self) -> None:
        state = dict(self.state.data)
        self.scene.selected_card = getattr(self, "_selected_card", None)
        self.scene.render_snapshot(state)
        self.refresh_prompt(state)

    def refresh_prompt(self, state: dict[str, Any]) -> None:
        """Draw what the server is waiting for. Pure: opens nothing, sends nothing."""
        while self.bid_layout.count():
            item = self.bid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        prompt = state.get("prompt")
        paused = state.get("paused")
        self.play_button.setEnabled(False)
        self.refresh_fold_button(state)

        if paused:
            self.statusBar().showMessage(
                "Gepauzeerd, wachten op: " + ", ".join(state.get("missing", []))
            )
            return
        if not prompt:
            return

        kind = prompt["kind"]
        if kind == "bid":
            for option in prompt["bid_options"]:
                button = QPushButton(bid_label(option))
                button.clicked.connect(lambda _checked, bid=option: self.on_bid_clicked(bid))
                self.bid_layout.addWidget(button)
        elif kind == "play":
            self.play_button.setEnabled(self._selected_card is not None)

    def refresh_fold_button(self, state: dict[str, Any]) -> None:
        """Show the fold offer, and how many have agreed so far.

        The server decides whether folding is on the table at all - the client
        neither knows nor guesses when a contract is beyond saving.
        """
        offered = bool(state.get("folding_offered"))
        self.fold_button.setVisible(offered)
        if not offered:
            self.fold_button.setChecked(False)
            return

        folded = state.get("folded") or []
        mine = state.get("your_seat")
        # setChecked without blocking would re-emit `clicked`? It does not -
        # only user interaction emits that - but the state must still follow the
        # server rather than the last click, in case the vote was refused.
        self.fold_button.setChecked(mine in folded)
        self.fold_button.setText(f"Ronde opgeven ({len(folded)}/4)")

    # --- reacting ----------------------------------------------------------

    _prompt_shown: dict[str, Any] | None = None
    _dialog_open = False

    def react_to_prompt(self, prompt: dict[str, Any] | None) -> None:
        """Open a dialog for the two prompts that need one, once each.

        Bidding and playing are answered with the widgets already on the table;
        only shuffling and cutting ask a question. Answering one is a side
        effect, so this runs from ``on_message`` and never from a refresh -
        otherwise every snapshot that still carried the shuffle prompt would
        open a second dialog on top of the first.
        """
        if self.state.get("paused"):
            # Nothing is asked of anyone while the table waits for a player.
            # The server re-offers the pending turn on resume, and the engine
            # never recorded having asked, so forgetting is the whole recovery.
            self._prompt_shown = None
            return
        if prompt == self._prompt_shown:
            return
        self._prompt_shown = prompt

        if not prompt:
            return
        kind = prompt["kind"]
        if kind not in ("shuffle", "cut") or self._dialog_open:
            return

        self._dialog_open = True
        try:
            if kind == "shuffle":
                answer = QMessageBox.question(
                    self,
                    "jwies",
                    "Wil je de kaarten schudden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                self.connection.send(
                    "answer_shuffle", shuffle=answer == QMessageBox.StandardButton.Yes
                )
            else:
                low, high = prompt["cut_minimum"], prompt["cut_maximum"]
                count, accepted = QInputDialog.getInt(
                    self,
                    "jwies",
                    f"Hoeveel kaarten neem je af? ({low} t.e.m. {high})",
                    (low + high) // 2,
                    low,
                    high,
                )
                if accepted:
                    self.connection.send("answer_cut", count=count)
        finally:
            self._dialog_open = False

    # --- outgoing ----------------------------------------------------------

    _selected_card: str | None = None

    def on_card_selected(self, code: str) -> None:
        self._selected_card = code
        prompt = self.state.get("prompt") or {}
        self.play_button.setEnabled(prompt.get("kind") == "play")

    def on_play_clicked(self) -> None:
        if self._selected_card:
            self.connection.send("play_card", card=self._selected_card)
            self._selected_card = None
            self.play_button.setEnabled(False)

    def on_bid_clicked(self, bid: dict[str, Any]) -> None:
        payload = dict(bid)
        if bid["type"] in SUIT_CHOOSING_BIDS:
            dialog = ChooseSuitDialog(allow_no_trump=bid["type"] == "solo", parent=self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            payload["suit"] = dialog.selected_suit()
        self.connection.send("place_bid", bid=payload)

    def on_last_trick_toggled(self, checked: bool) -> None:
        self.state.update(show_last_trick=checked)
        self.refresh_table()

    def on_chat_entered(self) -> None:
        text = self.chat_input.text().strip()
        if text:
            self.connection.send("chat_send", text=text)
            self.chat_input.clear()
