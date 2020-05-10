from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import uic

import sys
import os
import requests


class Controller(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

        self.setup_gui()
        self.log("Wies controller initiated")

    def setup_gui(self):
        # gui elements
        self.setWindowTitle("Wies controller")
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

    def log(self, txt):
        self.textbox.appendPlainText(txt)

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
        settings_pane = uic.loadUi("settings_pane.ui")
        settings_pane.exec_()



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

