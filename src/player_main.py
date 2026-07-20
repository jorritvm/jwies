import random
import sys

from PyQt6 import uic
from PyQt6.QtCore import QDataStream, Qt
from PyQt6.QtGui import QAction, QColor, QIcon, QTransform
from PyQt6.QtNetwork import QAbstractSocket, QTcpSocket
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsRectItem,
    QGraphicsScene,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from constants import (
    CARDSCALE,
    CARD_ROTATE,
    QDATASTREAMVERSION,
    SCENE_RECT_X,
    SCENE_RECT_Y,
    SIZEOF_UINT16,
    TEAM_COLOR_ATTACKERS,
    TEAM_COLOR_DEFENDERS,
    X_PLAYED_CARD,
    Y_PLAYED_CARD,
)
from paths import CONFIG_DIR, RESOURCES_DIR, UI_DIR
from player_helper_classes import ChooseSuitDialog, GraphicCard, MyGraphicsView
from player_helper_functions import (
    assemble_player_message,
    load_settings,
    timestamp_it,
)
from player_player import Player


class PlayerClient(QMainWindow):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.players: list[Player] = []  # contains player objects as defined in player_player

        # setup gui
        self.scene = QGraphicsScene()
        self.fieldrect = QGraphicsRectItem(1, 1, 798, 598)
        self.svgrenderer = QSvgRenderer(str(RESOURCES_DIR / "svg-cards.svg"))
        self.view = MyGraphicsView(self.fieldrect)
        self.btn_bidoptions: dict[str, QPushButton] = {}
        self.btnlasttrike = QPushButton("Toon laatste slag")
        self.btnplaycard = QPushButton("Speel kaart")
        self.buttonbox = QWidget()
        self.textbox = QPlainTextEdit()
        self.input_line = QLineEdit()
        self.chatbox = QWidget()
        self.score_label_attackers = None  # QGraphicsTextItem, created in setup_gui
        self.score_label_defenders = None  # QGraphicsTextItem, created in setup_gui
        self.setup_gui()

        # trick bookkeeping for the 'show last trick' feature
        self.current_trick: list[tuple[int, str]] = []  # list of (player_id, abbrev)
        self.last_trick: list[tuple[int, str]] = []
        self.last_trick_items: list[GraphicCard] = []  # cards currently shown

        self.settings = load_settings()

        # init TCP related stuff
        self.socket = QTcpSocket()
        self.next_block_size = 0
        self.socket.connected.connect(self.connected_handler)
        self.socket.readyRead.connect(self.read_server_message)
        self.socket.disconnected.connect(self.server_has_stopped)
        self.socket.errorOccurred.connect(lambda x: self.server_has_error(x))

        # debug shortcut: pop open connection pane right away
        # self.connect_to_a_game()

        # debug shortcut: connect right away
        # name = "player" + str(random.randint(1, 1000))
        # self.settings["last_connection"]["name"] = name
        # self.socket.connectToHost(
        #     self.settings["last_connection"]["host"],
        #     int(self.settings["last_connection"]["port"]),
        # )

    def setup_gui(self) -> None:
        # sizing policies
        minimum_policy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )
        expanding_policy = QSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        preferred_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        # gui elements
        self.setWindowTitle("jwies - player screen")
        self.setWindowIcon(QIcon(str(RESOURCES_DIR / "playing-card.png")))

        # set up the playing field
        self.scene.setBackgroundBrush(Qt.GlobalColor.darkGreen)
        self.scene.setSceneRect(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.scene.addItem(self.fieldrect)

        # trick counter per team (hidden until teams are formed)
        self.score_label_attackers = self.scene.addText("")
        self.score_label_attackers.setDefaultTextColor(QColor(TEAM_COLOR_ATTACKERS))
        self.score_label_attackers.setX(10)
        self.score_label_attackers.setY(8)
        self.score_label_attackers.setVisible(False)
        self.score_label_defenders = self.scene.addText("")
        self.score_label_defenders.setDefaultTextColor(QColor(TEAM_COLOR_DEFENDERS))
        self.score_label_defenders.setX(10)
        self.score_label_defenders.setY(28)
        self.score_label_defenders.setVisible(False)

        self.view.setScene(self.scene)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setSizePolicy(expanding_policy)

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

        spacer = QSpacerItem(
            20, 221, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        buttonbox_layout = QVBoxLayout()
        for btn in self.btn_bidoptions.values():
            buttonbox_layout.addWidget(btn)

        buttonbox_layout.addItem(spacer)

        self.btnlasttrike.setEnabled(False)
        self.btnlasttrike.setCheckable(True)
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
        self.btnlasttrike.toggled.connect(self.toggle_last_trick)

    def log(self, txt: str) -> None:
        msg = timestamp_it(txt)
        self.textbox.appendPlainText(msg)

    def connect_to_a_game(self) -> None:
        connect_pane = uic.loadUi(str(UI_DIR / "connect_pane.ui"))
        connect_pane.setWindowIcon(QIcon(str(RESOURCES_DIR / "network-hub.png")))

        # set initial value for dialog box
        connect_pane.line_name.setText(
            self.settings["last_connection"]["name"])
        # debug shortcut: set up a unique name instead of the one chosen by the player last time
        connect_pane.line_name.setText(
            "player" + str(random.randint(1, 1000))
        )
        # end debug
        connect_pane.line_host.setText(
            self.settings["last_connection"]["host"])
        connect_pane.spin_port.setValue(
            self.settings.getint("last_connection", "port"))

        if connect_pane.exec():
            # save new values in settings
            self.settings["last_connection"]["name"] = connect_pane.line_name.text()
            self.settings["last_connection"]["host"] = connect_pane.line_host.text()
            self.settings["last_connection"]["port"] = str(
                connect_pane.spin_port.value()
            )

            with open(CONFIG_DIR / "player.ini", "w") as settings_file:
                self.settings.write(settings_file)

            self.log("Player connections settings saved")

            # connect to the server
            self.log("Connecting to server...")
            self.socket.connectToHost(
                self.settings["last_connection"]["host"],
                int(self.settings["last_connection"]["port"]),
            )

    def connected_handler(self) -> None:
        msg = assemble_player_message(
            "LOGON", self.settings["last_connection"]["name"]
        )
        self.send_player_message(msg)

    def send_player_message(self, msg) -> None:
        self.socket.write(msg)

    def read_server_message(self) -> None:
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
                self.reset_round_visuals()
                for player in self.players:
                    player.set_dealer(False)
                    player.set_team_color(None)  # teams are not known yet
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
                self.reset_round_visuals()
                for player in self.players:
                    player.reset()
            if mtype == "HIDETRUMP":
                for player in self.players:
                    if player.is_dealer:
                        player.hide_trump_card()
            if mtype == "TEAMS":
                self.color_teams(mcontent)
            if mtype == "TRICKCOUNT":
                attacker_count, defender_count = mcontent.split(",")
                self.update_trick_count(attacker_count, defender_count)
            if mtype == "PLEASEPLAY":
                self.btnplaycard.setEnabled(True)
            if mtype == "CARD_WAS_PLAYED":
                player_id = mcontent.split(",")[0]
                abbrev = mcontent.split(",")[1]
                tricksize = mcontent.split(",")[2]
                self.btnplaycard.setEnabled(False)
                card_player = self.get_player_using_id(int(player_id))
                card_player.draw_played_card(abbrev, tricksize)
                self.current_trick.append((int(player_id), abbrev))
            if mtype == "CLEAN_GREEN":
                # the finished trick becomes the new 'last trick'
                self.btnlasttrike.setChecked(False)  # also removes shown cards
                self.clean_green()
                if len(self.current_trick) == 4:
                    self.last_trick = self.current_trick
                    self.btnlasttrike.setEnabled(True)
                self.current_trick = []

    def color_teams(self, mcontent: str) -> None:
        """color the player names per team: attackers and defenders each get their own color"""
        attacker_part, defender_part = mcontent.split("|")
        attacker_ids = [int(x) for x in attacker_part.split(",") if x != ""]
        defender_ids = [int(x) for x in defender_part.split(",") if x != ""]
        for player in self.players:
            if player.player_id in attacker_ids:
                player.set_team_color(TEAM_COLOR_ATTACKERS)
            elif player.player_id in defender_ids:
                player.set_team_color(TEAM_COLOR_DEFENDERS)
            else:
                player.set_team_color(None)

    def server_has_stopped(self) -> None:
        self.log("Socket error: Connection closed by server")
        self.socket.close()

    def server_has_error(self, error: QAbstractSocket.SocketError) -> None:
        self.log("Socket error: %s" % (self.socket.errorString()))
        self.log("Server error: %s" % error)
        self.socket.close()

    def send_chat(self) -> None:
        txt = self.input_line.text()
        self.send_chat_txt(txt)
        self.input_line.clear()

    def send_chat_txt(self, txt: str) -> None:
        msg = assemble_player_message("CHAT", txt)
        self.send_player_message(msg)

    def get_player_using_id(self, player_id: int) -> Player | None:
        for player in self.players:
            if player.player_id == player_id:
                return player
        return None

    def get_dealer_player(self) -> Player | None:
        for player in self.players:
            if player.is_dealer:
                return player
        return None

    def answer_to_shuffle_deck(self) -> None:
        # debug shortcut for debug purposes
        # self.send_chat_txt("Yes, reshuffle the deck.")
        # msg = assemble_player_message("RESHUFFLE", "YES")
        # self.send_player_message(msg)
        # end debug

        reply = QMessageBox.question(
            self,
            "Do you want to reshuffle the deck?",
            "Do you want to reshuffle the deck?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.send_chat_txt("Yes, reshuffle the deck.")
            msg = assemble_player_message("RESHUFFLE", "YES")
        else:
            self.send_chat_txt("No, do not reshuffle the deck.")
            msg = assemble_player_message("RESHUFFLE", "NO")
        self.send_player_message(msg)

    def answer_to_cut_deck(self, minmax: list[str]) -> None:
        # debug shortcut for debug purposes
        # num = 20
        # self.send_chat_txt("Cutting %i cards" % num)
        # msg = assemble_player_message("CUT", str(num))
        # self.send_player_message(msg)
        # end debug

        mincut = int(minmax[0])
        maxcut = int(minmax[1])
        num, ok = QInputDialog.getInt(
            self,
            "Cut deck",
            "How many cards do you want to slide under the deck?",
            random.randint(mincut, maxcut),
            mincut,
            maxcut,
        )
        if ok:
            self.send_chat_txt("Cutting %i cards" % num)
            msg = assemble_player_message("CUT", str(num))
            self.send_player_message(msg)
        else:
            self.answer_to_cut_deck(minmax)

    def enable_bid_options(self, bidoptions: list[str]) -> None:
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

    def bid(self, bid: str) -> None:
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
        elif bid == "misere_ouverte":
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

        # complete with server message
        self.send_chat_txt(txt)
        msg = assemble_player_message("BID", "%s,%s" % (bid, suit))
        self.send_player_message(msg)

        # reset the gui buttons
        for btn in self.btn_bidoptions.values():
            btn.setEnabled(False)

    def choose_suit_pre_bid(self, allow_no_trump: bool) -> str | None:
        """open suit selection dialog box and return the selected suit"""
        dlg = ChooseSuitDialog(allow_no_trump, self)
        if dlg.exec():
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
        return None

    def play_card(self) -> None:
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

    def clean_green(self) -> None:
        cards_on_table = self.scene.items()
        for card in cards_on_table:
            if card.zValue() > 10000:
                self.scene.removeItem(card)

    def update_trick_count(self, attacker_count: str, defender_count: str) -> None:
        """show/update the per-team trick counter in the top left corner"""
        self.score_label_attackers.setPlainText("Slagen aanval: %s" % attacker_count)
        self.score_label_defenders.setPlainText(
            "Slagen verdediging: %s" % defender_count
        )
        self.score_label_attackers.setVisible(True)
        self.score_label_defenders.setVisible(True)

    def toggle_last_trick(self, checked: bool) -> None:
        """show or hide the four cards of the last completed trick"""
        if checked:
            for i, (player_id, abbrev) in enumerate(self.last_trick):
                player = self.get_player_using_id(player_id)
                if player is None:
                    continue
                card = GraphicCard(abbrev, 20000 + i, self.svgrenderer, [])
                card.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                transformation = QTransform()
                transformation.scale(CARDSCALE, CARDSCALE)
                card.setX(X_PLAYED_CARD[player.seat])
                card.setY(Y_PLAYED_CARD[player.seat])
                transformation.rotate(CARD_ROTATE[player.seat])
                card.setTransform(transformation)
                self.scene.addItem(card)
                self.last_trick_items.append(card)
        else:
            for card in self.last_trick_items:
                if card.scene() is self.scene:
                    self.scene.removeItem(card)
            self.last_trick_items = []

    def reset_round_visuals(self) -> None:
        """clear trick bookkeeping and counters when a new round starts"""
        self.btnlasttrike.setChecked(False)
        self.btnlasttrike.setEnabled(False)
        self.current_trick = []
        self.last_trick = []
        self.score_label_attackers.setVisible(False)
        self.score_label_defenders.setVisible(False)


def main() -> None:
    app = QApplication(sys.argv)
    main_window = PlayerClient()
    main_window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
