from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtSvg import *
import pydealer as pd
import os
from staticvar import *



class Player():

    def __init__(self, id, name, seat, scene, svgrenderer):
        print("creating player with id " + str(id))
        self.id = int(id) # this is the id the server has for the player
        self.name = name
        self.seat = seat # this is the seat relative to where you are sitting (south)
        self.scene = scene
        self.svgrenderer = svgrenderer
        self.hand = list() # list of Graphic_Card objects

        self.setup_default_cards(seat)
        self.draw_name(seat, name)
        self.draw_hand()

        self.is_dealer = False
        self.trumpcard = None


    def setup_default_cards(self, seat):
        for z in range(13):
            card = Graphic_Card("back", z + 10, self.svgrenderer)
            self.hand.append(card)


    def draw_name(self, seat, name):
        name_label = self.scene.addText(name)
        name_label.setX(X_NAME[seat])
        name_label.setY(Y_NAME[seat])


    def receive_cards(self, card_abbreviation_list):
        # todo: remove dummy cards from the scene
        for card in self.hand:
            self.scene.removeItem(card)

        # sort the received cards and put them on my hand
        deck = pd.deck.Deck()
        stack = pd.stack.Stack(cards = deck.get_list(card_abbreviation_list))
        stack = self.sort_pdstack_on_hand(stack)
        z = 10
        for pdcard in stack:
            card = Graphic_Card(pdcard.abbrev, z, self.svgrenderer)
            self.hand.append(card)
            z += 1

        # draw them on the board
        self.draw_hand()


    def draw_hand(self):
        seat = self.seat
        for card in self.hand:
            transformation = QTransform()
            transformation.scale(CARDSCALE, CARDSCALE)
            card.setX(X_CARD[seat] + (card.z - 10) * XINC_CARD[seat])
            card.setY(Y_CARD[seat] + (card.z - 10) * YINC_CARD[seat])
            transformation.rotate(CARD_ROTATE[seat])
            card.setTransform(transformation)
            self.scene.addItem(card)


    def sort_pdstack_on_hand(self, stack):
        seq = list()
        for card in stack:
            v = 0
            if card.suit == "Diamonds":
                v += 100
            elif card.suit == "Spades":
                v += 200
            elif card.suit == "Hearts":
                v += 300
            if card.value == "Jack":
                v += 11
            elif card.value == "Queen":
                v += 12
            elif card.value == "King":
                v += 13
            elif card.value == "Ace":
                v += 14
            else:
                v += int(card.value) # 2 - 10
            seq.append(v)
        sorted_indices = sorted(range(len(seq)), key=seq.__getitem__)
        card_list = [stack[i] for i in sorted_indices]
        return_stack = pd.stack.Stack()
        return_stack.insert_list(card_list)
        return(return_stack)


    def draw_trump_card(self, abbrev):
        card = Graphic_Card(abbrev, 0, self.svgrenderer)
        transformation = QTransform()
        transformation.scale(CARDSCALE, CARDSCALE)
        card.setX(X_TRUMPCARD[self.seat])
        card.setY(Y_TRUMPCARD[self.seat])
        transformation.rotate(CARD_ROTATE[self.seat])
        card.setTransform(transformation)
        self.scene.addItem(card)
        self.trumpcard = card
        self.is_dealer = True


class Graphic_Card(QGraphicsSvgItem):

    def __init__(self, abbrev, z, svgrenderer, *args, **kwargs):
        super(Graphic_Card, self).__init__(*args, **kwargs)

        self.card_click = pyqtSignal(str)

        self.setSharedRenderer(svgrenderer)
        self.setZValue(z)

        self.z = z
        self.abbrev = abbrev

        if abbrev == "back":
            self.svgdescription = "back"
            self.setElementId(self.svgdescription)
        else:
            deck = pd.deck.Deck()
            self.pydealer_card = pd.tools.get_card(deck, abbrev)[1][0]
            self.suit = self.pydealer_card.suit
            self.value = self.pydealer_card.value
            self.svgdescription = self.get_svg_description()
            self.setElementId(self.svgdescription)


    def get_svg_description(self):
        v = self.value.lower()
        if v == "ace":
            v = "1"
        s = self.suit.lower()
        s = s[0:len(s)-1]
        desc = "%s_%s" % (v, s)
        return(desc)


    def mousePressEvent(self, event):
        if self.svgdescription != "back":
            print("clicked mouse on card " + str(self.z))
            print(self.sceneBoundingRect().topLeft().x(), self.sceneBoundingRect().topLeft().y())
            print(self.sceneBoundingRect().bottomRight().x(), self.sceneBoundingRect().bottomRight().y())
            #self.card_click.emit(str(self.z))


class Choose_suit_dialog(QDialog):

    def __init__(self, *args, **kwargs):
        super(Choose_suit_dialog, self).__init__(*args, **kwargs)

        self.setWindowTitle("Choose the suit you want for Trump...")

        suits = ["clubs", "diamonds", "spades", "hearts"]
        self.suitbuttons = list()
        for suit in suits:
            btn = QPushButton()
            pm = QPixmap(os.path.join("icons", suit + ".png"))
            qi = QIcon(pm)
            btn.setIcon(qi)
            btn.setIconSize(QSize(50,50))
            btn.setCheckable(True)
            self.suitbuttons.append(btn)
        suits_layout = QHBoxLayout()
        for btn in self.suitbuttons:
            suits_layout.addWidget(btn)
        topwidget = QWidget()
        topwidget.setLayout(suits_layout)

        QBtn = QDialogButtonBox.Ok
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)

        self.layout = QVBoxLayout()
        self.layout.addWidget(topwidget)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

