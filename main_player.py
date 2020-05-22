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

        self.oponents = list()

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
        pass

        # set up the bidoptions
        self.btn1 = QPushButton("1")
        self.btn2 = QPushButton("2")
        self.btn3 = QPushButton("3")
        self.btn4 = QPushButton("4")
        self.buttonbox_layout = QGridLayout()
        self.buttonbox_layout.addWidget(self.btn1, 0, 0)
        self.buttonbox_layout.addWidget(self.btn2, 0, 1)
        self.buttonbox_layout.addWidget(self.btn3, 1, 0)
        self.buttonbox_layout.addWidget(self.btn4, 1, 1)
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

        self.btn1.clicked.connect(lambda x: self.debug1())
        self.btn2.clicked.connect(lambda x: self.debug2())
        self.btn3.clicked.connect(lambda x: self.debug3())
        self.btn4.clicked.connect(lambda x: self.debug4())


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

            if mtype == "CHAT":
                self.textbox.appendPlainText(self.timestamp_it(mcontent))
            if mtype.startswith("SEAT"):
                id = mcontent.split(",")[0]
                name = mcontent.split(",")[1]
                seat = mtype.replace("SEAT","") # WEST NORTH EAST
                self.oponents.append(Oponent(id, name, seat, self.scene, self.svgrenderer))
            if mtype == "HAND":
                hand = mcontent.split(",")[0:13]

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
        msg = self.assemble_player_message("CHAT", txt)
        self.send_player_message(msg)
        self.input_line.clear()


    def abbrev_to_sorted_pydealer_card(self, abbrev_list):
        deck = pd.deck.Deck()
        stack = pd.stack.Stack(cards = deck.get_list(abbrev_list))
        stack.sort()
        return(stack)


    def debug(self):
        pass

    def debug1(self):
        self.oponents.append(Oponent(0, "ALFA", "WEST", self.scene, self.svgrenderer))

    def debug2(self):
        self.oponents.append(Oponent(0, "BETA", "NORTH", self.scene, self.svgrenderer))

    def debug3(self):
        self.oponents.append(Oponent(0, "GAMMA", "EAST", self.scene, self.svgrenderer))

    def debug4(self):
        pass


class Oponent():

    def __init__(self, id, name, seat, scene, svgrenderer):
        self.id = id
        self.name = name
        self.seat = seat
        self.scene = scene
        self.svgrenderer = svgrenderer
        self.cards = list()

        self.draw_cards_facedown(seat)
        self.draw_name(seat, name)

    def draw_cards_facedown(self, seat):
        if seat == "WEST":
            x = WEST_X
            y = WEST_Y
            xincrement = 0
            yincrement = Y_INCREMENT
        elif seat == "NORTH":
            x = NORTH_X
            y = NORTH_Y
            xincrement = X_INCREMENT
            yincrement = 0
        elif seat == "EAST":
            x = EAST_X
            y = EAST_Y
            xincrement = 0
            yincrement = -Y_INCREMENT
        else:
            return
        for z in range(13):
            transformation = QTransform()
            transformation.scale(CARDSCALE, CARDSCALE)
            card = Graphic_Card(52, z, self.svgrenderer)
            # card.scale(0.5) # CARDSCALE
            card.setX(x + z * xincrement)
            card.setY(y + z * yincrement)
            if seat == "WEST":
                transformation.rotate(90)
            elif seat == "NORTH":
                transformation.rotate(180)
            elif seat == "EAST":
                transformation.rotate(270)
            card.setTransform(transformation)
            self.cards.append(card)
            self.scene.addItem(card)


    def draw_name(self, seat, name):
        name_label = self.scene.addText(name)
        if seat == "WEST":
            name_label.setX(WESTNAME_X)
            name_label.setY(WESTNAME_Y)
        elif seat == "NORTH":
            name_label.setX(NORTHNAME_X)
            name_label.setY(NORTHNAME_Y)
        elif seat == "EAST":
            name_label.setX(EASTNAME_X)
            name_label.setY(EASTNAME_Y)


class Graphic_Card(QGraphicsSvgItem):

    def __init__(self, abbrev, zvalue, svgrenderer, *args, **kwargs):
        super(Graphic_Card, self).__init__(*args, **kwargs)

        self.card_click = pyqtSignal(str)

        self.setSharedRenderer(svgrenderer)
        self.setZValue(zvalue)

        self.zvalue = zvalue
        self.abbrev = abbrev

        deck = pd.deck.Deck()
        self.pydealer_card = pd.tools.get_card(deck, abbrev)[1][0]
        self.suit = self.pydealer_card.suit
        self.value = self.pydealer_card.value

        if index == 52:
            self.svgdescription = "back"
            self.setElementId(self.svgdescription)


    def get_svg_description(self):
        v = self.value.lower()
        if v = "ace":
            v = "1"
        s = self.suit.lower()
        s = s[0:len(s)-1]
        desc = "%s_%s" % (v, s)
        return(desc)


    def mousePressEvent(self, event):
        print("clicked mouse on card " + str(self.zvalue))
        #self.card_click.emit(str(self.zvalue))



app = QApplication(sys.argv)
main = PlayerClient()
main.show()
app.exec_()
