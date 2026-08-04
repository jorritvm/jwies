"""Graphics items and dialogs.

``GraphicCard`` takes the wire code and maps it directly to an SVG element id.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QResizeEvent
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from jwies_qt_client import ASSETS
from jwies_qt_client.cards import CARD_BACK, svg_element_id
from jwies_qt_client.layout import SELECT_ELEVATION, TRUMP_ELEVATION, Y_CARD

__all__ = ["CardSignals", "ChooseSuitDialog", "GraphicCard", "TableGraphicsView"]

SUIT_ICONS = {"C": "clubs", "D": "diamonds", "S": "spades", "H": "hearts"}
SUIT_ORDER = ["C", "D", "S", "H"]


class CardSignals(QWidget):
    """QGraphicsSvgItem is not a QObject subclass that can carry signals here,
    so selection is announced through this tiny helper instead."""

    selected = pyqtSignal(str)


class GraphicCard(QGraphicsSvgItem):
    """One card drawn from the shared svg-cards sheet."""

    def __init__(
        self,
        code: str,
        z: int,
        renderer: QSvgRenderer,
        hand: list[GraphicCard] | None = None,
        signals: CardSignals | None = None,
    ) -> None:
        super().__init__()
        self.code = code
        self.z = z
        self.hand = hand if hand is not None else []
        self.signals = signals
        self.is_selected = False
        self.is_trump_shown = False
        self.is_playable = False

        self.setSharedRenderer(renderer)
        self.setZValue(z)
        self.setElementId(svg_element_id(code))

    def base_y(self) -> float:
        """Resting y position in your own hand; the trump card stays lifted."""
        return Y_CARD["SOUTH"] - (TRUMP_ELEVATION if self.is_trump_shown else 0)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.code == CARD_BACK or not self.is_playable:
            return
        for card in self.hand:
            card.setY(card.base_y())
            card.is_selected = False
        self.setY(self.base_y() - SELECT_ELEVATION)
        self.is_selected = True
        if self.signals is not None:
            self.signals.selected.emit(self.code)


class ChooseSuitDialog(QDialog):
    """Pick a trump suit. Returns the wire suit code, or None for no trump."""

    def __init__(self, allow_no_trump: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kies je troefkleur")

        self.suit_buttons: list[tuple[str | None, QPushButton]] = []
        codes: list[str | None] = list(SUIT_ORDER)
        if allow_no_trump:
            codes.append(None)

        row = QHBoxLayout()
        for code in codes:
            button = QPushButton()
            button.setCheckable(True)
            if code is None:
                button.setText("Geen troef")
            else:
                icon = ASSETS / f"{SUIT_ICONS[code]}.png"
                button.setIcon(QIcon(QPixmap(str(icon))))
                button.setIconSize(QSize(50, 50))
            button.clicked.connect(lambda _checked, chosen=code: self._choose(chosen))
            self.suit_buttons.append((code, button))
            row.addWidget(button)

        holder = QWidget()
        holder.setLayout(row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(holder)
        layout.addWidget(buttons)
        self.setLayout(layout)

        self.chosen: str | None = SUIT_ORDER[0]
        self.suit_buttons[0][1].setChecked(True)

    def _choose(self, code: str | None) -> None:
        self.chosen = code
        for candidate, button in self.suit_buttons:
            button.setChecked(candidate == code)

    def selected_suit(self) -> str | None:
        return self.chosen


class TableGraphicsView(QGraphicsView):
    """Keeps the whole table visible whatever the window size."""

    def __init__(self, field: QGraphicsRectItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.field = field

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fitInView(self.field, Qt.AspectRatioMode.KeepAspectRatio)
