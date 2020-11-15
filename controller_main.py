import PyQt5.QtGui as qg
import PyQt5.QtWidgets as qw
import PyQt5.QtNetwork as qn
from PyQt5 import uic
import configparser
import requests
import sys
import os
import time
import staticvar as STATICVAR
import controller_table as ct


class Controller(qw.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(Controller, self).__init__(*args, **kwargs)

        self.setup_gui()
        self.settings = self.load_settings()
        self.log("Wies controller initiated")

        self.tcp_server = qn.QTcpServer(self)

        self.table = ct.Table(self)
        self.players = list()  # list of user defined player objects

        # start debug
        self.start_tcp_server(self.input_ip.text(), self.input_port.text())
        # end debug

    def setup_gui(self):
        # gui elements
        self.setWindowTitle("jwies - controller screen")
        self.setWindowIcon(qg.QIcon(os.path.join("icons", "server.png")))

        self.input_ip = qw.QLineEdit()
        self.input_ip.setText("127.0.0.1")

        self.input_port = qw.QLineEdit()
        self.input_port.setText("9999")

        self.start_server = qw.QPushButton("Start server")
        self.close_server = qw.QPushButton("Close server")
        self.close_server.setDisabled(True)

        self.textbox = qw.QPlainTextEdit()
        self.textbox.setReadOnly(True)

        # gui layout
        layout = qw.QVBoxLayout()
        layout.addWidget(self.input_ip)
        layout.addWidget(self.input_port)
        layout.addWidget(self.start_server)
        layout.addWidget(self.close_server)
        layout.addWidget(self.textbox)

        central_widget = qw.QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        self.resize(800, 600)

        # menu
        ip_dialog_action = qg.QAction("Get external IP address", self)
        settings_pane_action = qg.QAction("Game settings", self)
        menu_bar = self.menuBar()
        menu = menu_bar.addMenu("&Menu")
        menu.addAction(ip_dialog_action)
        menu.addAction(settings_pane_action)

        # signals & slots
        self.start_server.clicked.connect(
            lambda x: self.start_tcp_server(
                self.input_ip.text(), self.input_port.text()
            )
        )
        self.close_server.clicked.connect(lambda x: self.stop_tcp_server())
        ip_dialog_action.triggered.connect(lambda x: self.show_ip_dialog())
        settings_pane_action.triggered.connect(lambda x: self.show_settings_pane())

    def log(self, txt):
        msg = "(%s) %s" % (time.strftime("%H:%M:%S"), txt)
        self.textbox.appendPlainText(msg)

    def load_settings(self):
        settings = configparser.ConfigParser()
        settings.read(os.path.join("settings", "controller.ini"))
        return settings

    def get_ip(self):
        return requests.get("https://api.ipify.org").text

    def show_ip_dialog(self):
        # text, okPressed = \
        qw.QInputDialog.getText(
            self,
            "External ip lookup",
            "Your external ip is:",
            qw.QLineEdit.Normal,
            self.get_ip(),
        )

    def show_settings_pane(self):
        settings_pane = uic.loadUi(os.path.join("ui", "settings_pane.ui"))
        settings_pane.setWindowIcon(qg.QIcon(os.path.join("icons", "network-hub.png")))

        # set initial value for dialog box
        settings_pane.check_dealer_shuffle.setChecked(
            self.settings.getboolean("deal", "dealer_can_shuffle")
        )
        settings_pane.spin_split_minimum.setValue(
            self.settings.getint("deal", "minimum_cards_to_cut")
        )
        settings_pane.spin_split_maximum.setValue(
            self.settings.getint("deal", "maximum_cards_to_cut")
        )
        settings_pane.spin_deal_1.setValue(self.settings.getint("deal", "deal_1"))
        settings_pane.spin_deal_2.setValue(self.settings.getint("deal", "deal_2"))
        settings_pane.spin_deal_3.setValue(self.settings.getint("deal", "deal_3"))
        settings_pane.spin_deal_4.setValue(self.settings.getint("deal", "deal_4"))

        settings_pane.check_soloslim_plays_first.setChecked(
            self.settings.getboolean("bid", "soloslim_plays_first")
        )
        settings_pane.check_solo_plays_first.setChecked(
            self.settings.getboolean("bid", "solo_plays_first")
        )
        settings_pane.check_misere_ouverte_plays_first.setChecked(
            self.settings.getboolean("bid", "misere_ouverte_plays_first")
        )
        settings_pane.check_misere_plays_first.setChecked(
            self.settings.getboolean("bid", "misere_plays_first")
        )
        settings_pane.check_abondance_plays_first.setChecked(
            self.settings.getboolean("bid", "abondance_plays_first")
        )
        settings_pane.radio_trull_above_all_else.setChecked(
            self.settings.getboolean("bid", "trull_above_all_else")
        )
        settings_pane.radio_trull_not_above_all_else.setChecked(
            not self.settings.getboolean("bid", "trull_above_all_else")
        )
        settings_pane.check_soloslim_beats_trull.setChecked(
            self.settings.getboolean("bid", "soloslim_beats_trull")
        )
        settings_pane.check_solo_beats_trull.setChecked(
            self.settings.getboolean("bid", "solo_beats_trull")
        )
        settings_pane.check_misere_ouverte_beats_trull.setChecked(
            self.settings.getboolean("bid", "misere_ouverte_beats_trull")
        )

        if self.settings.getint("points", "trulltricks") == 8:
            settings_pane.radio_trull_8.setChecked(True)
        else:
            settings_pane.radio_trull_9.setChecked(True)
        settings_pane.spin_points_exact.setValue(
            self.settings.getint("points", "exact_amount_of_tricks")
        )
        settings_pane.spin_points_surpass.setValue(
            self.settings.getfloat("points", "extra_trick")
        )
        settings_pane.spin_points_abondance.setValue(
            self.settings.getint("points", "abundance")
        )
        settings_pane.spin_points_misere.setValue(
            self.settings.getint("points", "misere")
        )
        settings_pane.spin_points_misere_ouverte.setValue(
            self.settings.getint("points", "misere_ouverte")
        )
        settings_pane.spin_points_solo.setValue(self.settings.getint("points", "solo"))
        settings_pane.spin_points_soloslim.setValue(
            self.settings.getint("points", "solo_slim")
        )
        settings_pane.check_lose_double.setChecked(
            self.settings.getboolean("points", "losing_is_double")
        )
        settings_pane.check_pass_double.setChecked(
            self.settings.getboolean("points", "when_all_pass_points_are_double")
        )

        if settings_pane.exec_():
            # save new values in settings
            self.settings["deal"]["dealer_can_shuffle"] = (
                "True" if settings_pane.check_dealer_shuffle.isChecked() else "False"
            )
            self.settings["deal"]["minimum_cards_to_cut"] = str(
                settings_pane.spin_split_minimum.value()
            )
            self.settings["deal"]["maximum_cards_to_cut"] = str(
                settings_pane.spin_split_maximum.value()
            )
            self.settings["deal"]["deal_1"] = str(settings_pane.spin_deal_1.value())
            self.settings["deal"]["deal_2"] = str(settings_pane.spin_deal_2.value())
            self.settings["deal"]["deal_3"] = str(settings_pane.spin_deal_3.value())
            self.settings["deal"]["deal_4"] = str(settings_pane.spin_deal_4.value())

            self.settings["bid"]["soloslim_plays_first"] = (
                "True"
                if settings_pane.check_soloslim_plays_first.isChecked()
                else "False"
            )
            self.settings["bid"]["solo_plays_first"] = (
                "True" if settings_pane.check_solo_plays_first.isChecked() else "False"
            )
            self.settings["bid"]["misere_ouverte_plays_first"] = (
                "True"
                if settings_pane.check_misere_ouverte_plays_first.isChecked()
                else "False"
            )
            self.settings["bid"]["misere_plays_first"] = (
                "True"
                if settings_pane.check_misere_plays_first.isChecked()
                else "False"
            )
            self.settings["bid"]["abondance_plays_first"] = (
                "True"
                if settings_pane.check_abondance_plays_first.isChecked()
                else "False"
            )
            self.settings["bid"]["trull_above_all_else"] = (
                "True"
                if settings_pane.radio_trull_above_all_else.isChecked()
                else "False"
            )
            self.settings["bid"]["soloslim_beats_trull"] = (
                "True"
                if settings_pane.check_soloslim_beats_trull.isChecked()
                else "False"
            )
            self.settings["bid"]["solo_beats_trull"] = (
                "True" if settings_pane.check_solo_beats_trull.isChecked() else "False"
            )
            self.settings["bid"]["misere_ouverte_beats_trull"] = (
                "True"
                if settings_pane.check_misere_ouverte_beats_trull.isChecked()
                else "False"
            )

            if settings_pane.radio_trull_8.isChecked():
                self.settings["points"]["trulltricks"] = str(8)
            else:
                self.settings["points"]["trulltricks"] = str(9)
            self.settings["points"]["exact_amount_of_tricks"] = str(
                settings_pane.spin_points_exact.value()
            )
            self.settings["points"]["extra_trick"] = str(
                settings_pane.spin_points_surpass.value()
            )
            self.settings["points"]["abundance"] = str(
                settings_pane.spin_points_abondance.value()
            )
            self.settings["points"]["misere"] = str(
                settings_pane.spin_points_misere.value()
            )
            self.settings["points"]["misere_ouverte"] = str(
                settings_pane.spin_points_misere_ouverte.value()
            )
            self.settings["points"]["solo"] = str(
                settings_pane.spin_points_solo.value()
            )
            self.settings["points"]["solo_slim"] = str(
                settings_pane.spin_points_soloslim.value()
            )
            self.settings["points"]["losing_is_double"] = (
                "True" if settings_pane.check_lose_double.isChecked() else "False"
            )
            self.settings["points"]["when_all_pass_points_are_double"] = (
                "True" if settings_pane.check_pass_double.isChecked() else "False"
            )

            with open(os.path.join("settings", "controller.ini"), "w") as settings_file:
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
        self.log("Accepting new player")
        socket = self.tcp_server.nextPendingConnection()
        if socket is None:
            self.log("Error accepting new player: got invalid pending connection!")
        else:
            player_id = len(self.players)
            if player_id == 4:
                self.log(
                    "Error accepting new player: maximum amount of players connected reached (4)"
                )
            else:
                player = Player(player_id)
                self.players.append(player)
                player.socket = socket

                self.log("Connected a new player with ID %s" % str(player_id))
                socket.readyRead.connect(lambda: self.read_player_message(player_id))
                socket.disconnected.connect(lambda: self.remove_all_players(player_id))
                socket.disconnected.connect(socket.deleteLater)

    def remove_all_players(self, player_id):
        self.log(
            "Player with ID %i got disconnected, now removing all players" % player_id
        )
        self.serverchat(
            "Player %s got disconnected, now removing all players"
            % self.players[player_id].name
        )
        self.players = list()
        self.table = None

    def read_player_message(self, player_id):
        player = self.players[player_id]
        socket = player.socket
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

            mtype = stream.readQString()
            mcontent = stream.readQString()

            self.log(
                "%s socket message: [%s]-[%s]"
                % (self.players[player_id].name, mtype, mcontent)
            )

            player.next_block_size = 0

            # here we capture the messages that are for the controller
            if mtype == "LOGON":
                self.welcome_player(player, mcontent)
                enough = self.check_if_enough_players_are_connected()
                if enough:
                    self.table.prepare_first_game()
            elif mtype == "CHAT":
                msg = self.assemble_server_message(
                    "CHAT", player.name + ": " + mcontent
                )
                self.broadcast_server_message(msg)
            else:
                # here we pass all game related messages to the table
                self.table.handle_player_request(player, mtype, mcontent)

    def assemble_server_message(self, mtype, mcontent):
        self.log("Assembled server message: [%s]-[%s]" % (mtype, mcontent))
        msg = QByteArray()
        stream = QDataStream(msg, QIODevice.WriteOnly)
        stream.setVersion(QDATASTREAMVERSION)
        stream.writeUInt16(0)
        stream.writeQString(mtype)
        stream.writeQString(mcontent)
        stream.device().seek(0)
        stream.writeUInt16(msg.size() - SIZEOF_UINT16)
        return msg

    def send_server_message(self, player_id, msg):
        self.log("Sending server message to %s" % self.players[player_id].name)
        socket = self.players[player_id].socket
        socket.write(msg)

    def broadcast_server_message(self, msg):
        self.log("Broadcasting server message")
        for player in self.players:
            player.socket.write(msg)

    def serverchat(self, txt):
        msgtxt = "Controller: " + txt
        msg = self.assemble_server_message("CHAT", msgtxt)
        self.broadcast_server_message(msg)

    def welcome_player(self, player, playername):
        player.name = playername
        self.serverchat("welcome new player: " + playername)
        msg = self.assemble_server_message("YOUR_ID", str(player.id))
        self.send_server_message(player.id, msg)

    def check_if_enough_players_are_connected(self):
        i = len(self.players)
        enough = False
        if i < 4:
            self.serverchat(
                "%i out of 4 are players connected, waiting for more players to start the game."
                % i
            )
        elif i == 4:
            enough = True
        else:
            self.log(
                "Too many sockets connected, restart the controller application and start over"
            )
        return enough

    def dbug(self):
        print("close server clicked")


app = QApplication(sys.argv)
main = Controller()
main.show()
app.exec_()
