"""Everything before you sit down: connecting, and the list of tables.

Split out of ``main_window`` because it shares nothing with the table - no
snapshot, no prompt, no card scene. It talks to the rest through signals, so it
never sends a message itself and has no idea a server exists.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRegularExpression, Qt, pyqtSignal
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jwies_qt_client.settings import ClientSettings

__all__ = ["DEFAULT_TABLE_NAME", "STATUS_LABELS", "ConnectDialog", "LobbyPage"]

# Replaced with "Tafel van <naam>" as soon as the server tells us who we are.
DEFAULT_TABLE_NAME = "Onze tafel"

# The server's rule for a name, as far as a line edit can express it: letters,
# marks and digits from any script, plus the punctuation real names use.
#
# This only spares the player a round trip - the server decides, and says so in
# Dutch when it refuses. Kept deliberately no *stricter* than the server: a
# dialog that silently swallows a character the server would have accepted is
# worse than one that never checked, because there is nothing to read.
USERNAME_CHARACTERS = QRegularExpression(r"^[\p{L}\p{M}\p{N}_ .'\-]{0,20}$")

STATUS_LABELS = {
    "waiting": "wacht op spelers",
    "running": "bezig",
    "paused": "gepauzeerd",
    "finished": "afgelopen",
    "broken": "fout",
}


class ConnectDialog(QDialog):
    def __init__(self, settings: ClientSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Verbinden met een server")

        self.url_field = QLineEdit(settings.server_url)
        self.name_field = QLineEdit(settings.username)
        self.name_field.setMaxLength(20)
        self.name_field.setValidator(QRegularExpressionValidator(USERNAME_CHARACTERS, self))

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


class LobbyPage(QWidget):
    """The table list plus the form for making a new one."""

    join_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    # name, ruleset, scoring - the last two may be empty, meaning "server default"
    create_requested = pyqtSignal(str, str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<h2>Tafels</h2>"))
        self.lobby_list = QListWidget()
        layout.addWidget(self.lobby_list, 1)

        self.join_button = QPushButton("Deelnemen")
        self.delete_button = QPushButton("Verwijderen")
        self.refresh_button = QPushButton("Vernieuwen")
        row = QHBoxLayout()
        for button in (self.join_button, self.delete_button, self.refresh_button):
            row.addWidget(button)
        layout.addLayout(row)

        layout.addWidget(QLabel("<h3>Nieuwe tafel</h3>"))
        self.new_name = QLineEdit(DEFAULT_TABLE_NAME)
        self.ruleset_box = QComboBox()
        self.scoring_box = QComboBox()
        form = QFormLayout()
        form.addRow("Naam", self.new_name)
        form.addRow("Regelset", self.ruleset_box)
        form.addRow("Puntentelling", self.scoring_box)
        layout.addLayout(form)

        self.create_button = QPushButton("Tafel aanmaken")
        layout.addWidget(self.create_button)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: crimson")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.join_button.clicked.connect(lambda: self._with_selection(self.join_requested))
        self.delete_button.clicked.connect(lambda: self._with_selection(self.delete_requested))
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.create_button.clicked.connect(self._create)

    # --- what the server tells us ------------------------------------------

    def set_options(self, rulesets: list[str], scorings: list[str]) -> None:
        for box, values in ((self.ruleset_box, rulesets), (self.scoring_box, scorings)):
            box.clear()
            box.addItems(values)

    def suggest_a_table_name(self, username: str) -> None:
        """Name the table after whoever is making it.

        Table names have to be unique on a server, and everybody starting from
        the same suggestion means the second person to press the button gets
        refused for no reason they can see. Left alone once it has been edited.
        """
        if self.new_name.text() == DEFAULT_TABLE_NAME:
            self.new_name.setText(f"Tafel van {username}")

    def show_error(self, text: str) -> None:
        """Say what went wrong, here on the page where it went wrong.

        Errors used to go only to the chat log, which lives on the table page -
        so refusing to make a table looked exactly like the button doing
        nothing. "Er is al een lobby met die naam" is the common one, because
        the name field starts out the same for everybody.
        """
        self.error_label.setText(text)
        self.error_label.show()

    def show_lobbies(self, lobbies: list[dict[str, Any]]) -> None:
        self.error_label.hide()
        self.lobby_list.clear()
        for lobby in lobbies:
            status = STATUS_LABELS.get(lobby["status"], lobby["status"])
            item = QListWidgetItem(
                f"{lobby['name']} - {lobby['ruleset']} / {lobby['scoring']} - "
                f"{lobby['players']}/4 spelers - {status}"
            )
            item.setData(Qt.ItemDataRole.UserRole, lobby["id"])
            self.lobby_list.addItem(item)

    # --- what the player does ----------------------------------------------

    def _with_selection(self, signal: Any) -> None:
        item = self.lobby_list.currentItem()
        if item is not None:
            signal.emit(item.data(Qt.ItemDataRole.UserRole))

    def _create(self) -> None:
        name = self.new_name.text().strip()
        self.error_label.setVisible(not name)
        if not name:
            self.error_label.setText("Geef de tafel een naam.")
            return
        self.create_requested.emit(
            name, self.ruleset_box.currentText(), self.scoring_box.currentText()
        )
