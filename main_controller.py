from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import uic
import configparser

import sys
import os
import requests
import time

class Controller(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies controller initiated")

    def setup_gui(self):
        # gui elements
        self.setWindowTitle("jwies - controller screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "server.png")))

        self.input_ip = QLineEdit()
        self.input_ip.setText("localhost")

        self.input_port = QLineEdit()
        self.input_port.setText("9999")

        self.start_server = QPushButton("Start server")
        self.close_server = QPushButton("Close server")
        self.close_server.setDisabled(True)

        self.textbox = QPlainTextEdit()
        self.textbox.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.input_ip)
        layout.addWidget(self.input_port)
        layout.addWidget(self.start_server)
        layout.addWidget(self.close_server)
        layout.addWidget(self.textbox)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        ip_dialog_action = QAction("Get external IP address", self)
        settings_pane_action = QAction("Game settings", self)

        menubar = self.menuBar()
        menu = menubar.addMenu("&Menu")
        menu.addAction(ip_dialog_action)
        menu.addAction(settings_pane_action)

        self.resize(800, 600)

        # signals & slots
        self.start_server.clicked.connect(lambda x: self.start_tcp_server(self.input_ip.text(), self.input_port.text()))
        self.close_server.clicked.connect(lambda x: self.stop_tcp_server())
        ip_dialog_action.triggered.connect(lambda x: self.show_ip_dialog())
        settings_pane_action.triggered.connect(lambda x: self.show_settings_pane())

    def load_settings(self):
        settings = configparser.ConfigParser()
        settings.read(os.path.join("settings", "controller.ini"))
        return(settings)

    def log(self, txt):
        msg = "(%s) %s" % (time.strftime('%H:%M:%S'), txt)
        self.textbox.appendPlainText(msg)

    def get_ip(self):
        return(requests.get('https://api.ipify.org').text)

    def start_tcp_server(self, ip, port):
        self.tcp_server = TcpServer(self)
        if not self.tcp_server.listen(QHostAddress(ip), int(port)):
            self.log("Failed to start server: " + self.tcp_server.errorString())
        else:
            self.log("Server is running on ip %s and port %s" % (ip, port))
            self.start_server.setDisabled(True)
            self.close_server.setDisabled(False)

    def stop_tcp_server(self):
        self.tcp_server.close()
        self.log("Server is closed")
        self.start_server.setDisabled(False)
        self.close_server.setDisabled(True)

    def show_ip_dialog(self):
        text, okPressed = QInputDialog.getText(self, "External ip lookup", "Your external ip is:", QLineEdit.Normal, self.get_ip())

    def show_settings_pane(self):
        settings_pane = uic.loadUi(os.path.join("ui", "settings_pane.ui"))
        settings_pane.setWindowIcon(QIcon(os.path.join("icons", "network-hub.png")))

        # set initial value for dialog box
        settings_pane.check_dealer_shuffle.setChecked(self.settings.getboolean('game', 'dealer_can_shuffle'))
        settings_pane.check_misere_beats_trull.setChecked(self.settings.getboolean('game', 'misere_ouverte_beats_trull'))
        settings_pane.spin_split_minimum.setValue(self.settings.getint('game', 'minimum_cards_to_cut'))
        settings_pane.spin_split_maximum.setValue(self.settings.getint('game', 'maximum_cards_to_cut'))

        settings_pane.spin_points_exact.setValue(self.settings.getint('points', 'exact_amount_of_tricks'))
        settings_pane.spin_points_surpass.setValue(self.settings.getfloat('points', 'extra_trick'))
        settings_pane.spin_points_abondance.setValue(self.settings.getint('points', 'abundance'))
        settings_pane.spin_points_misere.setValue(self.settings.getint('points', 'misere'))
        settings_pane.spin_points_misere_ouverte.setValue(self.settings.getint('points', 'misere_ouverte'))
        settings_pane.spin_points_solo.setValue(self.settings.getint('points', 'solo'))
        settings_pane.spin_points_soloslim.setValue(self.settings.getint('points', 'solo_slim'))
        settings_pane.check_lose_double.setChecked(self.settings.getboolean('points', 'losing_is_double'))
        settings_pane.check_pass_double.setChecked(self.settings.getboolean('points', 'when_all_pass_points_are_double'))

        if settings_pane.exec_():
            # save new values in settings
            self.settings["game"]["dealer_can_shuffle"] = "True" if settings_pane.check_dealer_shuffle.isChecked() else "False"
            self.settings["game"]["misere_ouverte_beats_trull"] = "True" if settings_pane.check_misere_beats_trull.isChecked() else "False"
            self.settings["game"]["minimum_cards_to_cut"] = str(settings_pane.spin_split_minimum.value())
            self.settings["game"]["maximum_cards_to_cut"] = str(settings_pane.spin_split_maximum.value())

            self.settings["points"]["exact_amount_of_tricks"] = str(settings_pane.spin_points_exact.value())
            self.settings["points"]["extra_trick"] = str(settings_pane.spin_points_surpass.value())
            self.settings["points"]["abundance"] = str(settings_pane.spin_points_abondance.value())
            self.settings["points"]["misere"] = str(settings_pane.spin_points_misere.value())
            self.settings["points"]["misere_ouverte"] = str(settings_pane.spin_points_misere_ouverte.value())
            self.settings["points"]["solo"] = str(settings_pane.spin_points_solo.value())
            self.settings["points"]["solo_slim"] = str(settings_pane.spin_points_soloslim.value())
            self.settings["points"]["losing_is_double"] = "True" if settings_pane.check_lose_double.isChecked() else "False"
            self.settings["points"]["when_all_pass_points_are_double"] = "True" if settings_pane.check_pass_double.isChecked() else "False"

            with open(os.path.join("settings", "controller.ini"), 'w') as settings_file:
                self.settings.write(settings_file)

            self.log("Controller settings saved")


class TcpServer(QTcpServer):

    def __init__(self, *args, **kwargs):
        super(TcpServer, self).__init__(*args, **kwargs)

    def incomingConnection(self, socketId):
        socket = Socket(self)
        socket.setSocketDescriptor(socketId)


class Socket(QTcpSocket):

    def __init__(self,  *args, **kwargs):
        super(Socket, self).__init__( *args, **kwargs)

        # self.readyRead.connect()
        # self.connect(self, SIGNAL("readyRead()"), self.readRequest)
        # self.connect(self, SIGNAL("disconnected()"), self.deleteLater)
        # self.nextBlockSize = 0


app = QApplication(sys.argv)
main = Controller()
main.show()
app.exec_()

