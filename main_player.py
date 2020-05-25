from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtSvg import *
from PyQt5.QtNetwork import *

from PyQt5 import uic
import configparser
import pydealer as pd

import sys
import os
import time
import random

from staticvar import *


class PlayerClient(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(PlayerClient, self).__init__(*args, **kwargs)

        self.players = list() # contains player objects as defined in this module

        # init GUI and settings
        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies player initiated")  # self.connect_to_a_game()

        # init TCP related stuff
        self.socket = QTcpSocket()
        self.next_block_size = 0
        self.socket.connected.connect(self.connected_handler)
        self.socket.readyRead.connect(self.read_server_message)
        self.socket.readyRead.connect(self.debug)
        self.socket.disconnected.connect(self.server_has_stopped)
        self.socket.error.connect(lambda x: self.server_has_error(x))

        self.connect_to_a_game() # debug


    def setup_gui(self):
        # sizing policies
        fixed_policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        minimum_policy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        # gui elements
        self.setWindowTitle("jwies - player screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "playing-card.png")))

        # set up the playing field
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.svgrenderer = QSvgRenderer("svg/svg-cards.svg")
        self.view = QGraphicsView()
        self.view.setScene(self.scene)
        # self.timer = QTimeLine(1000)
        # self.timer.setCurveShape(QTimeLine.LinearCurve)
        # self.animation = QGraphicsItemAnimation();
        # self.animation.setTimeLine(self.timer)

        # set up the bidoptions
        self.btn_bidoptions = {"pass": QPushButton("Passen"),
                               "ask": QPushButton("Vragen"),
                               "join": QPushButton("Meegaan"),
                               "abondance": QPushButton("Abondance"),
                               "misere": QPushButton("Miserie"),
                               "alone": QPushButton("Alleen gaan")
                               }
        self.btnlasttrike = QPushButton("Toon laatste slag")
        self.playcard = QPushButton("Speel kaart")

        self.buttonbox_layout = QGridLayout()
        i = 0
        for btn in self.btn_bidoptions.values():
            self.buttonbox_layout.addWidget(btn, i % 2, i // 2)
            i += 1
        self.buttonbox_layout.addWidget(self.btnlasttrike, 0, 3)
        self.buttonbox_layout.addWidget(self.playcard, 1, 3)

        # ----- debug
        self.btn1 = QPushButton("1")
        self.btn2 = QPushButton("2")
        self.btn3 = QPushButton("3")
        self.btn4 = QPushButton("4")
        self.buttonbox_layout.addWidget(self.btn1, 2, 0)
        self.buttonbox_layout.addWidget(self.btn2, 2, 1)
        self.buttonbox_layout.addWidget(self.btn3, 2, 2)
        self.buttonbox_layout.addWidget(self.btn4, 2, 3)
        self.btn1.clicked.connect(lambda x: self.debug1())
        self.btn2.clicked.connect(lambda x: self.debug2())
        self.btn3.clicked.connect(lambda x: self.debug3())
        self.btn4.clicked.connect(lambda x: self.debug4())
        # ----- debug

        self.buttonbox = QWidget()
        self.buttonbox.setLayout(self.buttonbox_layout)

        # chat window
        self.textbox = QPlainTextEdit()
        self.textbox.setReadOnly(True)

        # chat input window
        self.input_line = QLineEdit()

        # layouts
        central_layout = QGridLayout()
        central_layout.addWidget(self.view, 0,0)
        central_layout.addWidget(self.buttonbox, 1, 0)
        central_layout.addWidget(self.textbox, 0, 1)
        central_layout.addWidget(self.input_line, 1, 1)

        self.btn1.setSizePolicy(minimum_policy)
        self.btn2.setSizePolicy(minimum_policy)
        self.btn3.setSizePolicy(minimum_policy)
        self.btn4.setSizePolicy(minimum_policy)
        self.input_line.setSizePolicy(minimum_policy)
        self.view.setSizePolicy(fixed_policy)

        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        # actions
        connect_action = QAction("Connect", self)
        about_action = QAction("About", self)
        debug_action = QAction("debug", self)

        menubar = self.menuBar()
        menu = menubar.addMenu("&Menu")
        menu.addAction(connect_action)
        menu.addAction(about_action)
        menu.addAction(debug_action)

        # signals & slots
        connect_action.triggered.connect(lambda x: self.connect_to_a_game())
        self.input_line.returnPressed.connect(self.send_chat)
        debug_action.triggered.connect(lambda x: self.debug())
        # todo this always send bid(alone)
        for item in self.btn_bidoptions.items():
            action = item[0]
            btn = item[1]
            btn.clicked.connect(lambda x: self.bid(action))


    def log(self, txt):
        msg = self.timestamp_it(txt)
        self.textbox.appendPlainText(msg)


    def load_settings(self):
        settings = configparser.ConfigParser()
        settings.read(os.path.join("settings", "player.ini"))
        return (settings)


    def connect_to_a_game(self):
        connect_pane = uic.loadUi(os.path.join("ui", "connect_pane.ui"))
        connect_pane.setWindowIcon(QIcon(os.path.join("icons", "network-hub.png")))

        # set initial value for dialog box
        connect_pane.line_name.setText(self.settings['last_connection']['name'])
        connect_pane.line_name.setText("player"+str(random.randint(1, 1000))) # for debug
        connect_pane.line_host.setText(self.settings['last_connection']['host'])
        connect_pane.spin_port.setValue(self.settings.getint('last_connection', 'port'))

        if connect_pane.exec_():
            # save new values in settings
            self.settings["last_connection"]["name"] = connect_pane.line_name.text()
            self.settings["last_connection"]["host"] = connect_pane.line_host.text()
            self.settings["last_connection"]["port"] = str(connect_pane.spin_port.value())

            with open(os.path.join("settings", "player.ini"), "w") as settings_file:
                self.settings.write(settings_file)

            self.log("Player connections settings saved")

            # connect to the server
            self.log("Connecting to server...")
            self.socket.connectToHost(self.settings["last_connection"]["host"], int(self.settings["last_connection"]["port"]))


    def connected_handler(self):
        msg = self.assemble_player_message("LOGON", self.settings["last_connection"]["name"])
        self.send_player_message(msg)


    def assemble_player_message(self, mtype, mcontent):
        msg = QByteArray()
        stream = QDataStream(msg, QIODevice.WriteOnly)
        stream.setVersion(QDATASTREAMVERSION)
        stream.writeUInt16(0)
        stream.writeQString(mtype)
        stream.writeQString(mcontent)
        stream.device().seek(0)
        stream.writeUInt16(msg.size() - SIZEOF_UINT16)
        return(msg)


    def send_player_message(self, msg):
        # self.next_block_size = 0
        print("writing my bytearray of size " + str(msg.size()))
        self.socket.write(msg)


    def read_server_message(self):
        print("now in function read server messages, bytes available:")
        print(self.socket.bytesAvailable())
        stream = QDataStream(self.socket)
        stream.setVersion(QDATASTREAMVERSION)

        # use a loop as multiple messages can be buffered onto the TCP socket already...
        while True:
            if self.next_block_size == 0:
                if self.socket.bytesAvailable() < SIZEOF_UINT16:
                    break
                self.next_block_size = stream.readUInt16()
            if self.socket.bytesAvailable() < self.next_block_size:
                break

            mtype = stream.readQString()
            mcontent = stream.readQString()

            print(mtype)
            print(mcontent)

            self.next_block_size = 0

            if mtype == "YOUR_ID":
                id = int(mcontent)
                self.players.append(Player(id, self.settings["last_connection"]["name"], "SOUTH", self.scene, self.svgrenderer))
            if mtype == "CHAT":
                self.textbox.appendPlainText(self.timestamp_it(mcontent))
            if mtype.startswith("SEAT"):
                id = mcontent.split(",")[0]
                name = mcontent.split(",")[1]
                seat = mtype.replace("SEAT","") # WEST NORTH EAST
                self.players.append(Player(id, name, seat, self.scene, self.svgrenderer))
            if mtype == "HAND":
                hand = mcontent.split(",")[0:13]
                print(hand)
                self.players[0].receive_cards(hand)
            if mtype == "TRUMPCARD":
                dealer_id = mcontent.split(",")[0]
                trump_card_abbrev = mcontent.split(",")[1]
                dealer = self.get_player_using_id(int(dealer_id))
                dealer.draw_trump_card(trump_card_abbrev)
            if mtype == "ASKBID":
                bidoptions = mcontent.split(",")
                self.enable_bid_options(bidoptions)

        print("i have left the loop")


    def server_has_stopped(self):
        self.log("Socket error: Connection closed by server")
        self.socket.close()


    def server_has_error(self, error):
        self.log("Socket error: %s" % (self.socket.errorString()))
        self.socket.close()


    def timestamp_it(self, s):
        x = "(" + time.strftime('%H:%M:%S') + ") " + s
        return(x)


    def send_chat(self):
        txt = self.input_line.text()
        self.send_chat_txt(txt)
        self.input_line.clear()

    def send_chat_txt(self, txt):
        msg = self.assemble_player_message("CHAT", txt)
        self.send_player_message(msg)

    def get_player_using_id(self, id):
        for player in self.players:
            if player.id == id:
                break
        return(player)


    def enable_bid_options(self, bidoptions):
        if "ask" in bidoptions:
            self.btnask.setEnabled(True)
        if "pass" in bidoptions:
            self.btnpass.setEnabled(True)
        if "join" in bidoptions:
            self.btnjoin.setEnabled(True)
        if "abondance" in bidoptions:
            self.btnabondance.setEnabled(True)
        if "misere" in bidoptions:
            self.btnmisere.setEnabled(True)
        if "alone" in bidoptions:
            self.btnalone.setEnabled(True)


    def bid(self, bid):
        # suit = self.players[0].trumpcard.suit # could be problem for trull
        suit = "Clubs" # debug

        if bid == "abondance":
            suit = self.choose_suit_pre_bid()
            if suit is None:
                return

        if suit == "Clubs":
            troef = "KLAVEREN"
        elif suit == "Diamonds":
            troef = "KOEKEN"
        elif suit == "Spades":
            troef = "SCHOPPEN"
        elif suit == "Hearts":
            troef = "HARTEN"

        if bid == "ask":
            txt = "IK GA " + troef + " VRAGEN"
        elif bid == "pass":
            txt = "IK GA PASSEN"
        elif bid == "join":
            txt = "IK GA MEE IN " + troef
        elif bid == "abondance":
            txt = "IK GA ABONDANCE IN DE " + troef
        elif bid == "misere":
            txt = "IK GA MISERIE"
        elif bid == "alone":
            txt = "IK GA ALLEEN GAAN"
        elif bid == "pass":
            txt = "IK GA PASSEN"

        # complete with server message
        self.send_chat_txt(txt)


    def choose_suit_pre_bid(self):
        dlg = Choose_suit_dialog(self)
        if dlg.exec_():
            for i in range(4):
                if dlg.suitbuttons[i].isChecked():
                    break
            suit = ["Clubs", "Diamonds", "Spades", "Hearts"][i]
            return(suit)
        else:
            return(None)



    def debug(self):
        pass

    def debug1(self):
        print("it's_a_meeee")

    def debug2(self):
        for player in self.players:
            print("player listing:")
            print(str(player.id))
            print(player.name)
            print(player.seat)

    def debug3(self):
        pass

    def debug4(self):
        dlg = Choose_suit_dialog(self)
        if dlg.exec_():
            for i in range(4):
                if dlg.suitbuttons[i].isChecked():
                    break
            suit = ["Clubs", "Diamonds", "Spades", "Hearts"][i]
            print("Success!")
            print(suit)
        else:
            print("Cancel!")


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


app = QApplication(sys.argv)
main = PlayerClient()
main.show()
app.exec_()
