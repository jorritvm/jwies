from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import uic
import configparser

import sys
import os
import time

from staticvar import *

class Player(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Player, self).__init__(*args, **kwargs)

        # init GUI and settings
        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies player initiated")  # self.connect_to_a_game()

        # init TCP related stuff
        self.socket = QTcpSocket()
        self.next_block_size = 0
        self.socket.connected.connect(self.connected_handler)
        self.socket.readyRead.connect(self.read_server_message)
        self.socket.disconnected.connect(self.server_has_stopped)
        self.socket.error.connect(lambda x: self.server_has_error(x))


    def setup_gui(self):
        # gui elements
        self.setWindowTitle("jwies - player screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "playing-card.png")))

        # table
        self.table = QLabel("playing field placeholder")

        # bidoptions
        self.bidoptions = QLabel("bidoptions placeholder")

        # chat window
        self.textbox = QPlainTextEdit()
        self.textbox.setReadOnly(True)

        # chat input window
        self.input_line = QLineEdit()

        # layouts
        layoutleft = QVBoxLayout()
        layoutleft.addWidget(self.table)
        layoutleft.addWidget(self.bidoptions)
        leftwidget = QWidget()
        leftwidget.setLayout(layoutleft)

        # layoutright = QVBoxLayout()
        rightsplitter = QSplitter()
        rightsplitter.setOrientation(Qt.Vertical)
        rightsplitter.addWidget(self.textbox)
        rightsplitter.addWidget(self.input_line)

        centralsplitter = QSplitter()
        centralsplitter.addWidget(leftwidget)
        centralsplitter.addWidget(rightsplitter)

        centrallayout = QHBoxLayout()
        centrallayout.addWidget(centralsplitter)
        central_widget = QWidget()
        central_widget.setLayout(centrallayout)
        self.setCentralWidget(central_widget)

        # actions
        connect_action = QAction("Connect", self)
        about_action = QAction("About", self)

        menubar = self.menuBar()
        menu = menubar.addMenu("&Menu")
        menu.addAction(connect_action)
        menu.addAction(about_action)

        # size
        self.resize(800, 600)

        # signals & slots
        connect_action.triggered.connect(lambda x: self.connect_to_a_game())
        self.input_line.returnPressed.connect(self.send_chat)

    def log(self, txt):
        msg = "(%s) %s" % (time.strftime('%H:%M:%S'), txt)
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
        self.socket.write(msg)


    def read_server_message(self):
        stream = QDataStream(self.socket)
        stream.setVersion(QDATASTREAMVERSION)

        #while True: # wrap everything in a while loop or not?
        if self.next_block_size == 0:
            if self.socket.bytesAvailable() < SIZEOF_UINT16:
                return
            self.next_block_size = stream.readUInt16()
        if self.socket.bytesAvailable() < self.next_block_size:
            return

        mtype = stream.readQString()
        mcontent = stream.readQString()

        self.next_block_size = 0

        if mtype == "CHAT":
            self.textbox.appendPlainText(self.timestamp_it(mcontent))


    def server_has_stopped(self):
        self.log("Error: Connection closed by server")
        self.socket.close()


    def server_has_error(self, error):
        self.log("Socket error: %s" % (self.socket.errorString()))
        self.socket.close()


    def receive_chat(self, mcontent):
        msg = "" + mcontent
        self.textbox.appendPlainText(mcontent)


    def timestamp_it(self, s):
        x = "(" + time.strftime('%H:%M:%S') + ") " + s
        return(x)


    def send_chat(self):
        txt = self.input_line.text()
        msg = self.assemble_player_message("CHAT", txt)
        self.send_player_message(msg)
        self.input_line.clear()


app = QApplication(sys.argv)
main = Player()
main.show()
app.exec_()
