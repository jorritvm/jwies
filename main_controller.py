from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtNetwork import *
from PyQt5 import uic
import configparser
import pydealer as pd
import requests

import sys
import os
import time
import random

from staticvar import *
from random import randint

class Controller(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies controller initiated")

        self.tcp_server = QTcpServer(self)
        self.next_block_size = 0 # maybe this should be a list of 4 to avoid racing issues?

        self.table = Table()
        self.players = list()


    def setup_gui(self):
        # gui elements
        self.setWindowTitle("jwies - controller screen")
        self.setWindowIcon(QIcon(os.path.join("icons", "server.png")))

        self.input_ip = QLineEdit()
        self.input_ip.setText("127.0.0.1")

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
        msg = "(%s) %s" % (time.strftime('%H:%M:%S'), txt)
        self.textbox.appendPlainText(msg)


    def load_settings(self):
        settings = configparser.ConfigParser()
        settings.read(os.path.join("settings", "controller.ini"))
        return(settings)


    def get_ip(self):
        return(requests.get('https://api.ipify.org').text)


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
        settings_pane.spin_deal_1.setValue(self.settings.getint('game', 'deal_1'))
        settings_pane.spin_deal_2.setValue(self.settings.getint('game', 'deal_2'))
        settings_pane.spin_deal_3.setValue(self.settings.getint('game', 'deal_3'))
        settings_pane.spin_deal_4.setValue(self.settings.getint('game', 'deal_4'))

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
            self.settings["game"]["deal_1"] = str(settings_pane.spin_deal_1.value())
            self.settings["game"]["deal_2"] = str(settings_pane.spin_deal_2.value())
            self.settings["game"]["deal_3"] = str(settings_pane.spin_deal_3.value())
            self.settings["game"]["deal_4"] = str(settings_pane.spin_deal_4.value())

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


    def start_tcp_server(self, ip, port):
        print("starting server for listening")
        if not self.tcp_server.listen(QHostAddress(ip), int(port)):
            self.log("Failed to start server: " + self.tcp_server.errorString())
        else:
            self.log("Server is running on ip %s and port %s" % (ip, port))
            self.start_server.setDisabled(True)
            self.close_server.setDisabled(False)
            self.tcp_server.newConnection.connect(self.accept_new_player)


    def stop_tcp_server(self):
        print("inside def stop server")
        self.tcp_server.close()
        self.log("Server is closed")
        self.start_server.setDisabled(False)
        self.close_server.setDisabled(True)


    def accept_new_player(self):
        # print("accepting new player")
        socket = self.tcp_server.nextPendingConnection()
        if (socket is None):
            # print("this socket sucks")
            self.log("Error: got invalid pending connection!")
        else:
            # todo: reject >4 players
            player_id = len(self.players)
            player = Player(player_id)
            self.players.append(player)
            player.socket = socket

            # print("created playerid %s" % str(player_id))
            socket.readyRead.connect(lambda: self.read_player_message(player_id))
            socket.disconnected.connect(socket.deleteLater)
            self.log("hooked up a new player")


    def read_player_message(self, player_id):
        print("reading player message with id: ")
        print(player_id)
        # use the tcpsocket of the correct player as IO device for the qdatastream
        player = self.players[player_id]
        socket = player.socket
        print("bytesavailable")
        print(socket.bytesAvailable())
        print("next block size")
        print(player.next_block_size)

        stream = QDataStream(socket)
        stream.setVersion(QDATASTREAMVERSION)

        # use a loop as multiple messages can be buffered onto the TCP socket already...
        while True:
            if player.next_block_size == 0:
                if socket.bytesAvailable() < SIZEOF_UINT16:
                    return
                player.next_block_size = stream.readUInt16()
            if socket.bytesAvailable() < player.next_block_size:
                return

            print("blocksize")
            print(player.next_block_size)

            mtype = stream.readQString()
            mcontent = stream.readQString()

            print("player x just said ...")
            print(player_id)
            print(mtype)
            print(mcontent)

            player.next_block_size = 0

            if mtype == "LOGON":
                self.welcome_player(player, mcontent)
                self.check_if_enough_players_are_connected()

            elif mtype == "CHAT":
                msg = self.assemble_server_message("CHAT", player.name + ": " + mcontent)
                self.broadcast_server_message(msg)
            else:
                self.log("Unrecognized request %s" % mtype)


    def assemble_server_message(self, mtype, mcontent):
        print("assembling server message")
        print(mtype)
        print(mcontent)
        msg = QByteArray()
        stream = QDataStream(msg, QIODevice.WriteOnly)
        stream.setVersion(QDATASTREAMVERSION)
        stream.writeUInt16(0)
        stream.writeQString(mtype)
        stream.writeQString(mcontent)
        stream.device().seek(0)
        stream.writeUInt16(msg.size() - SIZEOF_UINT16)
        return (msg)


    def send_server_message(self, player_id, msg):
        print("sending server message")
        self.log("Sending reply details...")
        socket = self.players[player_id].socket
        socket.write(msg)


    def broadcast_server_message(self, msg):
        print("broadcasting")
        for player in self.players:
            print(player.socket.write(msg))


    def serverchat(self, txt):
        msgtxt = "Controller: " + txt
        msg = self.assemble_server_message("CHAT", msgtxt)
        self.broadcast_server_message(msg)


    def welcome_player(self, player, playername):
        player.name = playername
        self.serverchat("welcome " + playername)


    def check_if_enough_players_are_connected(self):
        print("checking if we are 4")
        i = len(self.players)
        if i < 4:
            self.serverchat("%i out of 4 are players connected, waiting for more players to start the game." % i)
        elif i == 4:
            self.prepare_first_game()
        else:
            self.log("Too many sockets connected, restart the controller application and start over")


    def prepare_first_game(self):
        # give everyone a random seat and start the first round
        self.table.seats = self.players.copy()
        self.table.shuffle_seats()
        self.serverchat("Starting a new game. Sending everyone table layout now")
        for player in self.players:
            for direction in ("WEST", "NORTH", "EAST"):
                txt = self.table.neighbouring_player_info(player, direction)
                print("layout for player " + player.name)
                print("SEAT" + direction + " - " + txt)
                msg = self.assemble_server_message("SEAT" + direction, txt)
                self.send_server_message(player.id, msg)

        self.start_game()


    def start_game(self):
        # divide the cards
        r1 = self.settings.getint('game', 'deal_1')
        r2 = self.settings.getint('game', 'deal_2')
        r3 = self.settings.getint('game', 'deal_3')
        r4 = self.settings.getint('game', 'deal_4')
        self.table.divide_cards([r1,r2,r3,r4])

        # tell every player about their hand
        for player in self.players:
            player_hand_txt = ""
            for i in range(13):
                player_hand_txt += player.hand[i].abbrev + ","
                msg = self.assemble_server_message("HAND", player_hand_txt)
                self.send_server_message(player.id, msg)

    def dbug(self):
        print("close server clicked")


class Player:

    def __init__(self, id):
        self.id = id
        self.name = None
        self.socket = None
        self.hand = pd.Stack()
        self.next_block_size = 0
        # self.is_dealer = False


class Table:

    def __init__(self):
        self.seats = list() # a list of player instances
        self.dealer_seat = 0

        # create a shuffled deck of 52 cards
        self.deck = pd.Deck()
        self.deck.shuffle()

        # trick contains the card that players have played in the trick
        self.trick = pd.Stack()


    def shuffle_seats(self):
        random.shuffle(self.seats)


    def neighbouring_player_info(self, player_pov, relative_position):
        i = 0
        for seat in self.seats:
            if player_pov is seat:
                break
            i += 1
        if relative_position == "WEST":
            neighbour = self.seats[(i + 1) % 4]
        elif relative_position == "NORTH":
            neighbour = self.seats[(i + 2) % 4]
        elif relative_position == "EAST":
            neighbour = self.seats[(i + 3) % 4]
        returnstr = "%i,%s" % (neighbour.id, neighbour.name)
        return(returnstr)


    def divide_cards(self, roundsize):
        last_card_in_the_deck = self.deck[51]
        for i in range(roundsize):
            cards_to_deal_this_round = roundsize[i]
            for i in range(4):
                self.seat[self.dealer_seat + i + 1 % 4].hand.add(self.deck.deal(cards_to_deal_this_round))




app = QApplication(sys.argv)
main = Controller()
main.show()
app.exec_()

