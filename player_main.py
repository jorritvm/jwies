from PyQt5.QtNetwork import *
from PyQt5 import uic
import configparser
import sys
import time
import random
from player_player import *

class PlayerClient(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(PlayerClient, self).__init__(*args, **kwargs)

        self.players = list() # contains player objects as defined in this module

        # init GUI and settings
        self.setup_gui()
        self.settings = self.load_settings()

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
        minimum_policy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        expanding_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preferred_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # gui elements
        self.setWindowTitle("jwies - player screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "playing-card.png")))

        # set up the playing field
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.darkGreen)
        self.scene.setSceneRect(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.fieldrect = QGraphicsRectItem(1, 1, 798, 598)
        self.scene.addItem(self.fieldrect)
        self.svgrenderer = QSvgRenderer("svg/svg-cards.svg")
        self.view = MyGraphicsView(self.fieldrect)
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
        self.btn_bidoptions = {"pass": QPushButton("Passen"),
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
                               "alone": QPushButton("Alleen gaan")
                               }
        for btn in self.btn_bidoptions.values():
            btn.setEnabled(False)

        spacer = QSpacerItem(20, 221, QSizePolicy.Minimum, QSizePolicy.Expanding)

        buttonbox_layout = QVBoxLayout()
        for btn in self.btn_bidoptions.values():
            buttonbox_layout.addWidget(btn)

        spacerItem = QSpacerItem(20, 221, QSizePolicy.Minimum, QSizePolicy.Expanding)
        buttonbox_layout.addItem(spacer)

        self.btnlasttrike = QPushButton("Toon laatste slag")
        self.btnlasttrike.setEnabled(False)
        self.btnplaycard = QPushButton("Speel kaart")
        self.btnplaycard.setEnabled(False)
        buttonbox_layout.addWidget(self.btnlasttrike)
        buttonbox_layout.addWidget(self.btnplaycard)

        self.buttonbox = QWidget()
        self.buttonbox.setLayout(buttonbox_layout)

        for btn in self.btn_bidoptions.values():
            btn.setSizePolicy(minimum_policy)

        # chat window
        self.textbox = QPlainTextEdit()
        self.textbox.setReadOnly(True)
        self.textbox.setSizePolicy(preferred_policy)
        self.input_line = QLineEdit()
        self.input_line.setSizePolicy(minimum_policy)


        chat_layout = QVBoxLayout()
        chat_layout.addWidget(self.textbox)
        chat_layout.addWidget(self.input_line)
        self.chatbox = QWidget()
        self.chatbox.setLayout(chat_layout)

        # layouts
        central_layout = QHBoxLayout()
        central_layout.addWidget(self.view)
        central_layout.addWidget(self.buttonbox)
        central_layout.addWidget(self.chatbox)

        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

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
            btn.clicked.connect(lambda x, action=action: self.bid(action)) # special lambda parameter action

        # ----- debug
        debug_action = QAction("debug", self)
        menu.addAction(debug_action)
        debug_action.triggered.connect(lambda x: self.debug())

        self.btn1 = QPushButton("1")
        self.btn2 = QPushButton("2")
        self.btn3 = QPushButton("3")
        self.btn4 = QPushButton("4")
        buttonbox_layout.addWidget(self.btn1)
        buttonbox_layout.addWidget(self.btn2)
        buttonbox_layout.addWidget(self.btn3)
        buttonbox_layout.addWidget(self.btn4)
        self.btn1.clicked.connect(lambda x: self.debug1())
        self.btn2.clicked.connect(lambda x: self.debug2())
        self.btn3.clicked.connect(lambda x: self.debug3())
        self.btn4.clicked.connect(lambda x: self.debug4())

        self.resize(1200,600)
        # ----- end debug

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

    def get_dealer_player(self):
        for player in self.players:
            if player.is_dealer:
                break
        return(player)


    def enable_bid_options(self, bidoptions):
        opts = ["pass","ask","join","abondance","misere","alone"]
        for opt in opts:
            if opt in bidoptions:
                self.btn_bidoptions[opt].setEnabled(True)


    def bid(self, bid):
        dealer = self.get_dealer_player()
        suit = dealer.trumpcard.suit # could be problem for trull
        # suit = "Clubs" # debug

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
        msg = self.assemble_player_message("BID", "%s,%s" % (bid,suit))
        self.send_player_message(msg)

        # reset de knoppen
        for btn in self.btn_bidoptions.values():
            btn.setEnabled(False)


    def choose_suit_pre_bid(self):
        dlg = Choose_suit_dialog(self)
        if dlg.exec_():
            index = 0
            total = 0
            for i in range(4):
                if dlg.suitbuttons[i].isChecked():
                    index = i
                    total += 1
            if total == 1:
                suit = ["Clubs", "Diamonds", "Spades", "Hearts"][index]
                return(suit)
            else:
                return(None)



    def debug(self):
        # for btn in self.btn_bidoptions.values():
        #     btn.setEnabled(True)
        pass


    def debug1(self):
        # # for btn in self.btn_bidoptions.values():
        # #     btn.setEnabled(False)
        # print("debug1")
        # dealer = self.get_dealer_player()
        # print(dealer)
        # print(dealer.name)
        # print(dealer.__dict__)
        # print(dealer.trumpcard)
        # print(dealer.trumpcard.__dict__)
        # print(dealer.trumpcard.suit)  # could be problem for trull
        self.view.scale(1.2, 1.2)

    def debug2(self):
        # for player in self.players:
        #     print("player listing:")
        #     print(str(player.id))
        #     print(player.name)
        #     print(player.seat)
        card = Graphic_Card("AS", 1, self.svgrenderer)
        transformation = QTransform()
        transformation.scale(CARDSCALE, CARDSCALE)
        card.setX(100)
        card.setY(100)
        card.setTransform(transformation)
        self.c = card
        self.scene.addItem(self.c)

    def debug3(self):
        self.scene.removeItem(self.c)

    def debug4(self):
        pass
        # dlg = Choose_suit_dialog(self)
        # if dlg.exec_():
        #     for i in range(4):
        #         if dlg.suitbuttons[i].isChecked():
        #             break
        #     suit = ["Clubs", "Diamonds", "Spades", "Hearts"][i]
        #     print("Success!")
        #     print(suit)
        # else:
        #     print("Cancel!")

class MyGraphicsView(QGraphicsView):

    def __init__(self, fieldrect, *args, **kwargs):
        super(MyGraphicsView, self).__init__(*args, **kwargs)
        self.fieldrect = fieldrect

    def resizeEvent(self, event):
        self.fitInView(self.fieldrect, Qt.KeepAspectRatio)


app = QApplication(sys.argv)
main = PlayerClient()
main.show()
app.exec_()
