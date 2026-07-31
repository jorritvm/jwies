"""The main window: connect dialog, lobby list and card table.

All game logic is gone compared to the pre-refactor client. There is no ace
counting, no bid ladder, no "Troel!" chat: the window enables the buttons the
server's prompt names and draws the state the server sends.
"""

from __future__ import annotations

import logging
from importlib.resources import as_file
from typing import Any

from jwies_assets import CARD_DECK_SVG, asset_path, icon_path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

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

STATUS_LABELS = {
    "waiting": "wacht op spelers",
    "running": "bezig",
    "paused": "gepauzeerd",
    "finished": "afgelopen",
    "broken": "fout",
}

SUIT_CHOOSING_BIDS = {"ask", "abondance", "solo"}


def bid_label(bid: dict[str, Any]) -> str:
    """Dutch label for a bid option offered by the server."""
    text = BID_LABELS.get(bid["type"], bid["type"])
    if bid.get("tricks") is not None and bid["type"] in ("abondance", "alone"):
        text = f"{text} {bid['tricks']}"
    return text


class ConnectDialog(QDialog):
    def __init__(self, settings: ClientSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Verbinden met een server")

        self.url_field = QLineEdit(settings.server_url)
        self.name_field = QLineEdit(settings.username)
        self.name_field.setMaxLength(20)

        form = QFormLayout()
        form.addRow("Serveradres", self.url_field)
        form.addRow("Jouw naam", self.name_field)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(
            QLabel("Je naam is ook waarmee je terug aan tafel komt\nals je verbinding wegvalt.")
        )
        layout.addWidget(buttons)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def __init__(self, settings: ClientSettings) -> None:
        super().__init__()
        self.settings = settings
        self.state = ClientState()
        self.connection = ServerConnection(self)
        self.card_signals = CardSignals()

        self.setWindowTitle("jwies - Vlaamse wies")
        with as_file(icon_path("playing-card.png")) as path:
            self.setWindowIcon(QIcon(str(path)))
        self.resize(1100, 720)

        with as_file(asset_path(CARD_DECK_SVG)) as path:
            self.renderer = QSvgRenderer(str(path))

        self._build_ui()
        self._wire()

    # --- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_lobby_page())
        self.stack.addWidget(self._build_table_page())
        self.setCentralWidget(self.stack)

        menu = self.menuBar().addMenu("&Spel")
        connect_action = QAction("&Verbinden...", self)
        connect_action.triggered.connect(self.ask_to_connect)
        menu.addAction(connect_action)
        leave_action = QAction("Tafel &verlaten", self)
        leave_action.triggered.connect(lambda: self.connection.send("lobby_leave"))
        menu.addAction(leave_action)

        self.statusBar().showMessage("Niet verbonden")

    def _build_lobby_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("<h2>Tafels</h2>"))
        self.lobby_list = QListWidget()
        layout.addWidget(self.lobby_list, 1)

        row = QHBoxLayout()
        self.join_button = QPushButton("Deelnemen")
        self.delete_button = QPushButton("Verwijderen")
        self.refresh_button = QPushButton("Vernieuwen")
        row.addWidget(self.join_button)
        row.addWidget(self.delete_button)
        row.addWidget(self.refresh_button)
        layout.addLayout(row)

        layout.addWidget(QLabel("<h3>Nieuwe tafel</h3>"))
        form = QFormLayout()
        self.new_name = QLineEdit("Onze tafel")
        self.ruleset_box = QComboBox()
        self.scoring_box = QComboBox()
        form.addRow("Naam", self.new_name)
        form.addRow("Regelset", self.ruleset_box)
        form.addRow("Puntentelling", self.scoring_box)
        layout.addLayout(form)

        self.create_button = QPushButton("Tafel aanmaken")
        layout.addWidget(self.create_button)
        return page

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

        buttons = QWidget()
        button_layout = QVBoxLayout(buttons)
        button_layout.addWidget(self.bid_holder, 1)
        button_layout.addWidget(self.play_button)
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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(chat)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.addWidget(splitter)
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
        self.last_trick_button.toggled.connect(self.on_last_trick_toggled)
        self.chat_input.returnPressed.connect(self.on_chat_entered)

        self.create_button.clicked.connect(self.on_create_lobby)
        self.join_button.clicked.connect(self.on_join_lobby)
        self.delete_button.clicked.connect(self.on_delete_lobby)
        self.refresh_button.clicked.connect(lambda: self.connection.send("lobby_list"))

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
            self.ruleset_box.clear()
            self.ruleset_box.addItems(message.get("rulesets") or [])
            self.scoring_box.clear()
            self.scoring_box.addItems(message.get("scorings") or [])
            self.statusBar().showMessage(f"Verbonden als {message.get('username')}")
            if not message.get("current_lobby"):
                self.connection.send("lobby_list")
        elif kind == "chat":
            self.append_chat(message)
        elif kind == "error":
            self.append_chat({"text": message["text"], "kind": "system"})
            if message["code"] in ("username_taken", "username_invalid"):
                QMessageBox.warning(self, "jwies", message["text"])
        elif kind == "lobby_list":
            self.refresh_lobby_list()
        elif kind in ("player_joined", "player_left", "player_disconnected", "player_reconnected"):
            self.connection.send("lobby_list")

        if kind in ("game_started", "snapshot"):
            self.stack.setCurrentIndex(1)
        if self.state.get("in_game"):
            self.refresh_table()

    def append_chat(self, message: dict[str, Any]) -> None:
        sender = message.get("sender")
        text = message["text"]
        self.chat_log.appendPlainText(f"{sender}: {text}" if sender else text)

    def refresh_lobby_list(self) -> None:
        self.lobby_list.clear()
        for lobby in self.state.get("lobbies", []):
            status = STATUS_LABELS.get(lobby["status"], lobby["status"])
            item = QListWidgetItem(
                f"{lobby['name']} - {lobby['ruleset']} / {lobby['scoring']} - "
                f"{lobby['players']}/4 spelers - {status}"
            )
            item.setData(Qt.ItemDataRole.UserRole, lobby["id"])
            self.lobby_list.addItem(item)

    def refresh_table(self) -> None:
        state = dict(self.state.data)
        self.scene.selected_card = getattr(self, "_selected_card", None)
        self.scene.render_snapshot(state)
        self.refresh_prompt(state)

    def refresh_prompt(self, state: dict[str, Any]) -> None:
        while self.bid_layout.count():
            item = self.bid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        prompt = state.get("prompt")
        paused = state.get("paused")
        self.play_button.setEnabled(False)

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
        elif kind == "shuffle":
            answer = QMessageBox.question(
                self,
                "jwies",
                "Wil je de kaarten schudden?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            self.connection.send("answer_shuffle", shuffle=answer == QMessageBox.StandardButton.Yes)
        elif kind == "cut":
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

    def on_create_lobby(self) -> None:
        name = self.new_name.text().strip()
        if not name:
            QMessageBox.warning(self, "jwies", "Geef de tafel een naam.")
            return
        self.connection.send(
            "lobby_create",
            name=name,
            ruleset=self.ruleset_box.currentText() or None,
            scoring=self.scoring_box.currentText() or None,
        )

    def _selected_lobby_id(self) -> str | None:
        item = self.lobby_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_join_lobby(self) -> None:
        lobby_id = self._selected_lobby_id()
        if lobby_id:
            self.connection.send("lobby_join", lobby_id=lobby_id)

    def on_delete_lobby(self) -> None:
        lobby_id = self._selected_lobby_id()
        if lobby_id:
            self.connection.send("lobby_delete", lobby_id=lobby_id)
