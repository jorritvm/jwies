from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import uic
import configparser

import sys
import os
import time

class Player(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Player, self).__init__(*args, **kwargs)

        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies player initiated")  # self.connect_to_a_game()

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
        self.inputbox = QPlainTextEdit()

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
        rightsplitter.addWidget(self.inputbox)

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
        # self.start_server.clicked.connect(lambda x: self.start_tcp_server(self.input_ip.text(), self.input_port.text()))
        # self.close_server.clicked.connect(lambda x: self.stop_tcp_server())
        # settings_pane_action.triggered.connect(lambda x: self.show_settings_pane())

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

            self.log("Player settings saved")

app = QApplication(sys.argv)
main = Player()
main.show()
app.exec_()
