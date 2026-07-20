import pydealer as pd
import pydealer.tools as pdtools
from PyQt6.QtCore import QSize, Qt
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

from constants import SELECT_ELEVATION, TRUMP_ELEVATION, Y_CARD
from paths import RESOURCES_DIR


class GraphicCard(QGraphicsSvgItem):
    def __init__(
        self,
        abbrev: str,
        z: int,
        svgrenderer: QSvgRenderer,
        hand: list,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        # todo: check if/why we need argument hand here ...

        # self.card_click = pyqtSignal(str)
        self.hand = hand

        self.setSharedRenderer(svgrenderer)
        self.setZValue(z)

        self.z = z
        self.abbrev = abbrev

        self.is_selected = False
        self.is_trump_shown = False  # True while this own-hand card is shown as trump

        if abbrev == "back":
            self.svgdescription = "back"
            self.setElementId(self.svgdescription)
        else:
            deck = pd.deck.Deck()
            self.pydealer_card = pdtools.get_card(deck, abbrev)[1][0]
            self.suit = self.pydealer_card.suit
            self.value = self.pydealer_card.value
            self.svgdescription = self.get_svg_description()
            self.setElementId(self.svgdescription)

    def get_svg_description(self) -> str:
        """translate pydealer suit and value into svg card descriptor"""
        v = self.value.lower()
        if v == "ace":
            v = "1"
        s = self.suit.lower()
        s = s[0:len(s) - 1]
        desc = "%s_%s" % (v, s)
        return desc

    def base_y(self) -> int:
        """resting y position of this card in the own hand (trump stays elevated)"""
        return Y_CARD["SOUTH"] - (TRUMP_ELEVATION if self.is_trump_shown else 0)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.svgdescription != "back":
            for card in self.hand:
                card.setY(card.base_y())
                card.is_selected = False
            self.setY(self.base_y() - SELECT_ELEVATION)
            self.is_selected = True
            # self.card_click.emit(str(self.z))


class ChooseSuitDialog(QDialog):
    def __init__(self, allow_no_trump: bool, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.setWindowTitle("Choose the suit you want for Trump...")

        suits = ["clubs", "diamonds", "spades", "hearts"]
        if allow_no_trump:
            suits.append(None)
        self.suitbuttons: list[QPushButton] = []
        for suit in suits:
            btn = QPushButton()
            if suit is not None:
                pm = QPixmap(str(RESOURCES_DIR / (suit + ".png")))
                qi = QIcon(pm)
                btn.setIcon(qi)
                btn.setIconSize(QSize(50, 50))
            else:
                btn.setText("Geen troef")
            btn.setCheckable(True)
            self.suitbuttons.append(btn)
        suits_layout = QHBoxLayout()
        for btn in self.suitbuttons:
            suits_layout.addWidget(btn)
        topwidget = QWidget()
        topwidget.setLayout(suits_layout)

        qbtn = QDialogButtonBox.StandardButton.Ok
        self.buttonBox = QDialogButtonBox(qbtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.layout.addWidget(topwidget)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class MyGraphicsView(QGraphicsView):
    def __init__(self, fieldrect: QGraphicsRectItem, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fieldrect = fieldrect

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.fitInView(self.fieldrect, Qt.AspectRatioMode.KeepAspectRatio)
