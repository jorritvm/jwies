from PyQt5.QtCore import Qt
from PyQt5.QtNetwork import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtSvg import *
from PyQt5 import uic
import os.path
import sys
import random

from player_player import Player, ChooseSuitDialog, MyGraphicsView
from player_helper_functions import *


class PlayerClient(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(PlayerClient, self).__init__(*args, **kwargs)

        self.players = list()  # contains player objects as defined in this module

        # setup gui
        self.scene = QGraphicsScene()
        self.fieldrect = QGraphicsRectItem(1, 1, 798, 598)
        self.svgrenderer = QSvgRenderer("img/svg-cards.svg")
        self.view = MyGraphicsView(self.fieldrect)
        self.btn_bidoptions = None
        self.btnlasttrike = QPushButton("Toon laatste slag")
        self.btnplaycard = QPushButton("Speel kaart")
        self.buttonbox = QWidget()
        self.textbox = QPlainTextEdit()
        self.input_line = QLineEdit()
        self.chatbox = QWidget()
        self.setup_gui()

        self.settings = load_settings()

        # init TCP related stuff
        self.socket = QTcpSocket()
        self.next_block_size = 0
        self.socket.connected.connect(self.connected_handler)
        self.socket.readyRead.connect(self.read_server_message)
        self.socket.disconnected.connect(self.server_has_stopped)
        self.socket.error.connect(lambda x: self.server_has_error(x))

        # debug
        # pop open connection pane right away
        # self.connect_to_a_game()
        # connect right away
        name = "player" + str(random.randint(1, 1000))
        self.settings["last_connection"]["name"] = name
        self.socket.connectToHost(
            self.settings["last_connection"]["host"],
            int(self.settings["last_connection"]["port"]),
        )
        # end debug

    def setup_gui(self):  # sizing policies
        minimum_policy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        expanding_policy = QSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        preferred_policy = QSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Expanding)

        # gui elements
        self.setWindowTitle("jwies - player screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "playing-card.png")))

        # set up the playing field
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.scene.addItem(self.fieldrect)

        self.view.setScene(self.scene)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setSizePolicy(expanding_policy)

        # self.view.setFixedHeight(600)
        # self.view.setFixedWidth(800)
        # self.timer = QTimeLine(1000)
        # self.timer.setCurveShape(QTimeLine.LinearCurve)
        # self.animation = QGraphicsItemAnimation();
        # self.animation.setTimeLine(self.timer)

        # set up the buttonbox : bidoptions & play buttons
        self.btn_bidoptions = {
            "pass": QPushButton("Passen"),
            "ask": QPushButton("Vragen"),
            "join": QPushButton("Meegaan"),
            "abon9": QPushButton("Abondance_9"),
            "misere": QPushButton("Miserie"),
            "abon10": QPushButton("Abondance_10"),
            "abon11": QPushButton("Abondance_11"),
            "abon12": QPushButton("Abondance_12"),
            "misere_ouverte": QPushButton("Miserie bloot"),
            "solo": QPushButton("Solo"),
            "soloslim": QPushButton("Solo slim"),
            "alone": QPushButton("Alleen gaan"),
        }
        for btn in self.btn_bidoptions.values():
            btn.setEnabled(False)

        spacer = QSpacerItem(20, 221, QSizePolicy.Minimum,
                             QSizePolicy.Expanding)

        buttonbox_layout = QVBoxLayout()
        for btn in self.btn_bidoptions.values():
            buttonbox_layout.addWidget(btn)

        # spacer_item = QSpacerItem(
        #     20, 221, QSizePolicy.Minimum, QSizePolicy.Expanding)
        buttonbox_layout.addItem(spacer)

        self.btnlasttrike.setEnabled(False)
        self.btnplaycard.setEnabled(False)
        self.btnplaycard.setMinimumHeight(40)
        buttonbox_layout.addWidget(self.btnlasttrike)
        buttonbox_layout.addWidget(self.btnplaycard)

        self.buttonbox.setLayout(buttonbox_layout)

        for btn in self.btn_bidoptions.values():
            btn.setSizePolicy(minimum_policy)

        # chat window
        self.textbox.setReadOnly(True)
        self.textbox.setSizePolicy(preferred_policy)
        self.input_line.setSizePolicy(minimum_policy)

        chat_layout = QVBoxLayout()
        chat_layout.addWidget(self.textbox)
        chat_layout.addWidget(self.input_line)
        self.chatbox.setLayout(chat_layout)

        # layouts
        central_layout = QHBoxLayout()
        central_layout.addWidget(self.view)
        central_layout.addWidget(self.buttonbox)
        left_widget = QWidget()
        left_widget.setLayout(central_layout)

        # splitter
        splitter = QSplitter()
        splitter.addWidget(left_widget)
        splitter.addWidget(self.chatbox)
        # central_layout.addWidget(self.chatbox)

        # central_widget = QWidget()
        # central_widget.setLayout(central_layout)
        # self.setCentralWidget(central_widget)
        self.setCentralWidget(splitter)

        # menu bar
        connect_action = QAction("Connect", self)
        about_action = QAction("About", self)

        menubar = self.menuBar()
        menu = menubar.addMenu("&Menu")
        menu.addAction(connect_action)
        menu.addAction(about_action)

        # signals & slots
        connect_action.triggered.connect(lambda x: self.connect_to_a_game())
        self.input_line.returnPressed.connect(self.send_chat)
        for item in self.btn_bidoptions.items():
            action = item[0]
            btn = item[1]
            btn.clicked.connect(
                lambda x, lamba_action=action: self.bid(lamba_action)
            )  # special lambda parameter action
        self.btnplaycard.clicked.connect(
            lambda x: self.play_card()
        )  # special lambda parameter action

    def log(self, txt):
        msg = timestamp_it(txt)
        self.textbox.appendPlainText(msg)

    def connect_to_a_game(self):
        connect_pane = uic.loadUi(os.path.join("ui", "connect_pane.ui"))
        connect_pane.setWindowIcon(
            QIcon(os.path.join("icons", "network-hub.png")))

        # set initial value for dialog box
        connect_pane.line_name.setText(
            self.settings["last_connection"]["name"])
        # start debug
        connect_pane.line_name.setText(
            "player" + str(random.randint(1, 1000))
        )
        # end debug
        connect_pane.line_host.setText(
            self.settings["last_connection"]["host"])
        connect_pane.spin_port.setValue(
            self.settings.getint("last_connection", "port"))

        if connect_pane.exec_():
            # save new values in settings
            self.settings["last_connection"]["name"] = connect_pane.line_name.text()
            self.settings["last_connection"]["host"] = connect_pane.line_host.text()
            self.settings["last_connection"]["port"] = str(
                connect_pane.spin_port.value()
            )

            with open(os.path.join("settings", "player.ini"), "w") as settings_file:
                self.settings.write(settings_file)

            self.log("Player connections settings saved")

            # connect to the server
            self.log("Connecting to server...")
            self.socket.connectToHost(
                self.settings["last_connection"]["host"],
                int(self.settings["last_connection"]["port"]),
            )

    def connected_handler(self):
        msg = assemble_player_message(
            "LOGON", self.settings["last_connection"]["name"]
        )
        self.send_player_message(msg)

    def send_player_message(self, msg):
        self.socket.write(msg)

    def read_server_message(self):
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

            self.next_block_size = 0

            if mtype == "YOUR_ID":
                player_id = int(mcontent)
                self.players.append(
                    Player(
                        player_id,
                        self.settings["last_connection"]["name"],
                        "SOUTH",
                        self.scene,
                        self.svgrenderer,
                    )
                )
            if mtype == "CHAT":
                self.textbox.appendPlainText(timestamp_it(mcontent))
            if mtype.startswith("SEAT"):
                player_id = mcontent.split(",")[0]
                name = mcontent.split(",")[1]
                seat = mtype.replace("SEAT", "")  # WEST NORTH EAST
                self.players.append(
                    Player(player_id, name, seat, self.scene, self.svgrenderer)
                )
            if mtype == "DEALERID":
                for player in self.players:
                    player.set_dealer(False)
                    player.restore_default_cards()
                dealer = self.get_player_using_id(int(mcontent))
                dealer.set_dealer(True)
            if mtype == "SHUFFLEDECK":
                self.answer_to_shuffle_deck()
            if mtype == "CUTDECK":
                self.answer_to_cut_deck(mcontent.split(","))
            if mtype == "HAND":
                hand = mcontent.split(",")[0:13]
                self.players[0].receive_cards(hand)
                if self.players[0].amount_of_aces_on_hand() >= 3:
                    self.send_chat_txt("Troel!")
                else:
                    self.send_chat_txt("Pas troel!")
            if mtype == "TRUMPCARD":
                dealer_id = mcontent.split(",")[0]
                trump_card_abbrev = mcontent.split(",")[1]
                dealer = self.get_player_using_id(int(dealer_id))
                dealer.draw_trump_card(trump_card_abbrev)
            if mtype == "ASKBID":
                bidoptions = mcontent.split(",")
                self.enable_bid_options(bidoptions)
            if mtype == "REDEAL":
                for player in self.players:
                    player.reset()
            if mtype == "HIDETRUMP":
                for player in self.players:
                    if player.is_dealer:
                        player.hide_trump_card()
            if mtype == "PLEASEPLAY":
                self.btnplaycard.setEnabled(True)
            if mtype == "CARD_WAS_PLAYED":
                player_id = mcontent.split(",")[0]
                abbrev = mcontent.split(",")[1]
                tricksize = mcontent.split(",")[2]
                self.btnplaycard.setEnabled(False)
                card_player = self.get_player_using_id(int(player_id))
                card_player.draw_played_card(abbrev, tricksize)
            if mtype == "CLEAN_GREEN":
                self.clean_green()


    def server_has_stopped(self):
        self.log("Socket error: Connection closed by server")
        self.socket.close()

    def server_has_error(self, error):
        self.log("Socket error: %s" % (self.socket.errorString()))
        self.log("Server error: %s" % error)
        self.socket.close()

    def send_chat(self):
        txt = self.input_line.text()
        self.send_chat_txt(txt)
        self.input_line.clear()

    def send_chat_txt(self, txt):
        msg = assemble_player_message("CHAT", txt)
        self.send_player_message(msg)

    def get_player_using_id(self, player_id):
        player = None
        for player in self.players:
            if player.player_id == player_id:
                break
        return player

    def get_dealer_player(self):
        player = None
        for player in self.players:
            if player.is_dealer:
                break
        return player

    def answer_to_shuffle_deck(self):
        # shortcut for debug purposes
        self.send_chat_txt("Yes, reshuffle the deck.")
        msg = assemble_player_message("RESHUFFLE", "YES")
        self.send_player_message(msg)

        # msgbox = QMessageBox()
        # msgbox.setIcon(QMessageBox.Question)
        # msgbox.setText("Do you want to reshuffle the deck?")
        # msgbox.setWindowTitle("Do you want to reshuffle the deck?")
        # msgbox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        # reply = msgbox.exec()
        # if reply == QMessageBox.Yes:
        #     self.send_chat_txt("Yes, reshuffle the deck.")
        #     msg = assemble_player_message("RESHUFFLE", "YES")
        # else:
        #     self.send_chat_txt("No, do not reshuffle the deck.")
        #     msg = assemble_player_message("RESHUFFLE", "NO")
        # self.send_player_message(msg)

    def answer_to_cut_deck(self, minmax):
        # shortcut for debug purposes
        num = 20
        self.send_chat_txt("Cutting %i cards" % num)
        msg = assemble_player_message("CUT", str(num))
        self.send_player_message(msg)

        # mincut = int(minmax[0])
        # maxcut = int(minmax[1])
        # num, ok = QInputDialog.getInt(
        #     self,
        #     "Cut deck",
        #     "How many cards do you want to slide under the deck?",
        #     random.randint(mincut, maxcut),
        #     mincut,
        #     maxcut,
        # )
        # if ok:
        #     self.send_chat_txt("Cutting %i cards" % num)
        #     msg = assemble_player_message("CUT", str(num))
        #     self.send_player_message(msg)
        # else:
        #     self.answer_to_cut_deck(minmax)

    def enable_bid_options(self, bidoptions):
        opts = [
            "pass",
            "ask",
            "join",
            "abon9",
            "misere",
            "abon10",
            "abon11",
            "abon12",
            "misere_ouverte",
            "solo",
            "soloslim",
            "alone",
        ]
        for opt in opts:
            if opt in bidoptions:
                self.btn_bidoptions[opt].setEnabled(True)

    def bid(self, bid):
        dealer = self.get_dealer_player()
        suit = dealer.trumpcard.suit  # could be problem for trull

        if bid in ["abon9", "abon10", "abon11", "abon12"]:
            suit = self.choose_suit_pre_bid(False)
            if suit is None:
                return
        if bid == "solo":
            suit = self.choose_suit_pre_bid(True)
            if suit is None:
                return

        troef = ""
        if suit == "Clubs":
            troef = "KLAVEREN"
        elif suit == "Diamonds":
            troef = "KOEKEN"
        elif suit == "Spades":
            troef = "SCHOPPEN"
        elif suit == "Hearts":
            troef = "HARTEN"
        elif suit == "no_trump":
            troef = "ZONDER TROEF"

        txt = ""
        if bid == "ask":
            txt = "IK GA " + troef + " VRAGEN"
        elif bid == "pass":
            txt = "IK GA PASSEN"
        elif bid == "join":
            txt = "IK GA MEE IN " + troef
        elif bid == "abon9":
            txt = "IK GA ABONDANCE 9 SLAGEN IN DE " + troef
        elif bid == "misere":
            txt = "IK GA MISERIE"
        elif bid == "misere_ouvere":
            txt = "IK GA MISERIE BLOOT"
        elif bid == "abon10":
            txt = "IK GA ABONDANCE 10 SLAGEN IN DE " + troef
        elif bid == "abon11":
            txt = "IK GA ABONDANCE 11 SLAGEN IN DE " + troef
        elif bid == "abon12":
            txt = "IK GA ABONDANCE 12 SLAGEN IN DE " + troef
        elif bid == "solo":
            txt = "IK GA SOLO IN DE " + troef
        elif bid == "soloslim":
            txt = "IK GA SOLO SLIM (troef: %s)" % troef
        elif bid == "alone":
            txt = "IK GA ALLEEN GAAN"
        elif bid == "pass":
            txt = "IK GA PASSEN"

        # complete with server message
        self.send_chat_txt(txt)
        msg = assemble_player_message("BID", "%s,%s" % (bid, suit))
        self.send_player_message(msg)

        # reset the gui buttons
        for btn in self.btn_bidoptions.values():
            btn.setEnabled(False)

    def choose_suit_pre_bid(self, allow_no_trump):
        """open suit selection dialog box and return the selected suit"""
        dlg = ChooseSuitDialog(allow_no_trump, self)
        if dlg.exec_():
            index = 0
            total = 0
            for i in range(4 + int(allow_no_trump)):
                if dlg.suitbuttons[i].isChecked():
                    index = i
                    total += 1
            if total == 1:
                suits = ["Clubs", "Diamonds", "Spades", "Hearts"]
                if allow_no_trump:
                    suits.append("no_trump")
                suit = suits[index]
                return suit
            else:
                return None

    def play_card(self):
        i = 0
        abbrev = ""
        for card in self.players[0].hand:
            if card.is_selected:
                i += 1
                abbrev = card.abbrev
        if i == 1:
            self.btnplaycard.setEnabled(False)
            msg = assemble_player_message("IPLAY", abbrev)
            self.send_player_message(msg)

    def clean_green(self):
        cards_on_table = self.scene.items()
        for card in cards_on_table:
            if card.zValue() > 10000:
                self.scene.removeItem(card)

app = QApplication(sys.argv)
main = PlayerClient()
main.show()
app.exec_()
