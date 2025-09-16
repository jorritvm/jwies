from PyQt5.QtCore import Qt
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtSvg import *
import pydealer as pd
import pydealer.tools as pdtools
import os

from constants import *


class GraphicCard(QGraphicsSvgItem):
    def __init__(self, abbrev, z, svgrenderer, hand, *args, **kwargs):
        super(GraphicCard, self).__init__(*args, **kwargs)

        # todo: check if/why we need argument hand here ...

        # self.card_click = pyqtSignal(str)
        self.hand = hand

        self.setSharedRenderer(svgrenderer)
        self.setZValue(z)

        self.z = z
        self.abbrev = abbrev

        self.is_selected = False

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

    def get_svg_description(self):
        """translate pydealer suit and value into svg card descriptor"""
        v = self.value.lower()
        if v == "ace":
            v = "1"
        s = self.suit.lower()
        s = s[0:len(s) - 1]
        desc = "%s_%s" % (v, s)
        return desc

    def mousePressEvent(self, event):
        if self.svgdescription != "back":
            for card in self.hand:
                card.setY(Y_CARD["SOUTH"])
                card.is_selected = False
            self.setY(Y_CARD["SOUTH"] - 40)
            self.is_selected = True
            # self.card_click.emit(str(self.z))


class ChooseSuitDialog(QDialog):
    def __init__(self, allow_no_trump, *args, **kwargs):
        super(ChooseSuitDialog, self).__init__(*args, **kwargs)

        self.setWindowTitle("Choose the suit you want for Trump...")

        suits = ["clubs", "diamonds", "spades", "hearts"]
        if allow_no_trump:
            suits.append(None)
        self.suitbuttons = list()
        for suit in suits:
            btn = QPushButton()
            if suit is not None:
                pm = QPixmap(os.path.join("img", suit + ".png"))
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

        qbtn = QDialogButtonBox.Ok
        self.buttonBox = QDialogButtonBox(qbtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.layout.addWidget(topwidget)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class MyGraphicsView(QGraphicsView):
    def __init__(self, fieldrect, *args, **kwargs):
        super(MyGraphicsView, self).__init__(*args, **kwargs)
        self.fieldrect = fieldrect

    def resizeEvent(self, event):
        self.fitInView(self.fieldrect, Qt.KeepAspectRatio)