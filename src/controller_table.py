import pydealer as pd
import random


class Player:
    def __init__(self, player_id):
        self.player_id = player_id
        self.name = ""
        self.socket = None
        self.hand = pd.Stack()
        self.next_block_size = 0
        # self.is_dealer = False

    def amount_of_aces_on_hand(self):
        i = 0
        for card in self.hand:
            if card.value == "Ace":
                i += 1
        return i

    def suit_of_my_single_ace(self):
        for card in self.hand:
            if card.value == "Ace":
                return card.suit
        return None

    def has_kh(self):
        i_have_it = False
        for card in self.hand:
            if card.value == "King" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it

    def has_qh(self):
        i_have_it = False
        for card in self.hand:
            if card.value == "Queen" and card.suit == "Hearts":
                i_have_it = True
        return i_have_it


class Table:
    def __init__(self, ctrl):
        self.ctrl = ctrl  # this way we have access to the communication functions
        self.settings = self.ctrl.settings

        self.seats = list()  # a list of player instances
        self.dealer_seat = 0
        self.player_to_play_card = None

        # create a shuffled deck of 52 cards
        self.deck = pd.Deck()
        self.deck.shuffle()

        # trick info
        self.last_card_before_dealing = None
        self.seat_to_bid = (
            self.dealer_seat + 1
        ) % 4  # player left from dealer starts to bid
        self.trickbids = [
            list(),
            list(),
            list(),
        ]  # list 1: bid action, list 2: trump, list 3: who made the bid

        self.trick = list()  # list of [player, pdcard]
        self.tricks = list()  # list of tricks

        # two teams
        self.attackers = list()
        self.defenders = list()
        self.trump = None
        self.type_of_game = None

    def get_player_from_id(self, player_id):
        """ returns a Player() object linked to the given id"""
        x = None
        for player in self.seats:
            if player.player_id == player_id:
                x = player
        return x

    def handle_player_request(self, player, mtype, mcontent):
        if mtype == "RESHUFFLE":
            if mcontent == "YES":
                self.deck.shuffle()
            self.ask_to_cut_deck()

        elif mtype == "CUT":
            self.cut_deck(int(mcontent))
            self.divide_cards()
            self.initiate_bidding()

        elif mtype == "BID":
            self.process_a_new_bid(player, mcontent)

        elif mtype == "IPLAY":
            self.process_played_card(player, mcontent)

    def prepare_first_game(self):
        print("prepare_first_game")
        # give everyone a random seat
        self.seats = self.ctrl.players.copy()
        random.shuffle(self.seats)
        print("seats have been shuffled")
        self.ctrl.serverchat(
            "Starting a new game. Sending everyone table seat positions."
        )
        # inform all players of who sits where
        for player in self.seats:
            for direction in ("WEST", "NORTH", "EAST"):
                neighbour_info = self.neighbouring_player_info(player, direction)
                txt = "%i,%s" % (neighbour_info[0], neighbour_info[1])
                msg = self.ctrl.assemble_server_message("SEAT" + direction, txt)
                print("informing players who sits where")
                self.ctrl.send_server_message(player.player_id, msg)

        # start the game
        self.start_game()

    def neighbouring_player_info(self, player_pov, relative_position):
        """
        this function provides, for a given player and his relative position (east, west, north)
        what other player is sitting there
        """
        print("neighbour player info method")
        print("player pov")
        print(player_pov)
        print("seats")
        for seat in self.seats:
            print(seat)

        i = 0
        for seat in self.seats:
            if player_pov is seat:
                break
            i += 1

        neighbour = None
        if relative_position == "WEST":
            neighbour = self.seats[(i + 1) % 4]
        elif relative_position == "NORTH":
            neighbour = self.seats[(i + 2) % 4]
        elif relative_position == "EAST":
            neighbour = self.seats[(i + 3) % 4]

        print("ready to return")
        return [neighbour.player_id, neighbour.name]

    def start_game(self):
        print("def start game")
        dealer = self.seats[self.dealer_seat]
        # tell all players who the dealer is
        self.ctrl.serverchat("The dealer for this round is: %s" % dealer.name)
        msg = self.ctrl.assemble_server_message("DEALERID", str(dealer.player_id))
        self.ctrl.broadcast_server_message(msg)

        # check if the dealer wants to shuffle
        if self.settings["deal"]["dealer_can_shuffle"] == "True":
            self.ctrl.serverchat(
                "Asking dealer "
                + dealer.name
                + " if he wishes to shuffle the deck of cards."
            )
            msg = self.ctrl.assemble_server_message("SHUFFLEDECK", "no_message")
            self.ctrl.send_server_message(dealer.player_id, msg)
        else:
            self.ask_to_cut_deck()

    def ask_to_cut_deck(self):
        cutter_seat = self.dealer_seat - 1
        cutter = self.seats[cutter_seat]

        mincut = str(self.settings["deal"]["minimum_cards_to_cut"])
        maxcut = str(self.settings["deal"]["maximum_cards_to_cut"])

        self.ctrl.serverchat(
            "Player %s can now cut the deck by taking between %s and %s cards"
            % (cutter.name, mincut, maxcut)
        )
        msg = self.ctrl.assemble_server_message("CUTDECK", "%s,%s" % (mincut, maxcut))
        self.ctrl.send_server_message(cutter.player_id, msg)

    def cut_deck(self, num):
        self.deck = pd.stack.Stack(cards=self.deck[num:52] + self.deck[0:num])

    def divide_cards(self):
        # divide the cards
        r1 = self.settings.getint("deal", "deal_1")
        r2 = self.settings.getint("deal", "deal_2")
        r3 = self.settings.getint("deal", "deal_3")
        r4 = self.settings.getint("deal", "deal_4")
        self.ctrl.serverchat(
            "Dealer will now deal cards as follows: %i-%i-%i-%i" % (r1, r2, r3, r4)
        )
        roundsize = [r1, r2, r3, r4]

        self.last_card_before_dealing = self.deck[
            0
        ]  # deck deals from the end of the list so the last card is index 0
        self.ctrl.log(
            "last card before dealing = " + self.last_card_before_dealing.abbrev
        )  # debug

        for cards_to_deal_this_round in roundsize:
            for i in range(4):
                self.seats[(self.dealer_seat + i + 1) % 4].hand.add(
                    self.deck.deal(cards_to_deal_this_round)
                )

        # tell every player about their hand
        for player in self.seats:
            player_hand_txt = ""
            for i in range(13):
                player_hand_txt += player.hand[i].abbrev + ","
            msg = self.ctrl.assemble_server_message("HAND", player_hand_txt)
            self.ctrl.send_server_message(player.player_id, msg)

    def initiate_bidding(self):
        we_need_to_bid = True

        if self.check_for_trull():
            self.add_default_trull_player_bids()
            if self.settings["bid"]["trull_above_all_else"] == "True":
                # trump goes above all else, there will be no more bidding so we don't show the trump card
                we_need_to_bid = False

        if we_need_to_bid:
            # show this game's trump card (last card dealt)
            dealer = self.seats[self.dealer_seat]
            trump_card = self.last_card_before_dealing.abbrev
            msg = self.ctrl.assemble_server_message(
                "TRUMPCARD", str(dealer.player_id) + "," + trump_card
            )
            self.ctrl.broadcast_server_message(msg)

            # start bidding round
            player_to_bid = self.get_player_to_bid()
            bid_options = self.get_remaining_bid_options()
            self.ctrl.serverchat(
                "Start bidding round. Please bid, %s" % player_to_bid.name
            )
            msg = self.ctrl.assemble_server_message("ASKBID", bid_options)
            self.ctrl.send_server_message(player_to_bid.player_id, msg)
        else:
            self.initiate_playing_of_cards()

    def check_for_trull(self):
        it_is_trull = False
        for player in self.seats:
            if player.amount_of_aces_on_hand() >= 3:
                it_is_trull = True
        return it_is_trull

    def add_default_trull_player_bids(self):
        lead_player = None
        second_player = None
        trump_suit = None
        for player in self.seats:
            if player.amount_of_aces_on_hand() >= 3:
                lead_player = player
            if player.amount_of_aces_on_hand() == 1:
                second_player = player
                trump_suit = player.suit_of_my_single_ace()
        if second_player is None:
            trump_suit = "Hearts"
            khplayer = None
            qhplayer = None
            for player in self.seats:
                if player.has_kh():
                    khplayer = player
                if player.has_qh():
                    qhplayer = player
            if khplayer != lead_player:
                second_player = khplayer
            else:
                second_player = qhplayer
        self.add_bid(["trull1", trump_suit, lead_player])
        self.add_bid(["trull2", trump_suit, second_player])

    def get_player_to_bid(self):
        """the next player to bid is simply the one to the left, and, if one asked, and three passed
        he who asked has a final say"""
        bids = self.trickbids[0]
        if "trull1" not in bids:
            if len(bids) < 4:
                return self.seats[self.seat_to_bid]
            elif len(bids) == 4:
                if "ask" in bids and bids.count("pass") == 3:
                    id_of_player_to_bid = self.trickbids[2][bids.index("ask")]
                    return self.get_player_from_id(id_of_player_to_bid)
                else:
                    return None
            else:
                return None
        else:
            # trull
            if len(bids) < 6:
                return self.seats[self.seat_to_bid]
            else:
                return None

    def add_bid(self, newbid, default_trull_bid=False):
        action = newbid[0]
        suit = newbid[1]
        player = newbid[2]
        # even if a player already bid, and has to do a final bid, we append it! (so trickbids > 4)
        self.trickbids[0].append(action)  # what type of bid was made?
        self.trickbids[1].append(suit)  # if a specific suit was given, log it
        self.trickbids[2].append(player)  # who made the bid - a Player object
        if not default_trull_bid:
            self.seat_to_bid = (self.seat_to_bid + 1) % 4

    def process_a_new_bid(self, player, mcontent):
        # process the received bid
        newbid = mcontent.split(",")  # 2 elements: bid and suit
        newbid.append(player)
        self.add_bid(newbid)

        # identify the next step to take
        player_to_bid = self.get_player_to_bid()  # player object
        if player_to_bid is not None:
            bid_options = self.get_remaining_bid_options()
            self.ctrl.serverchat("Please bid, %s" % player_to_bid.name)
            msg = self.ctrl.assemble_server_message("ASKBID", bid_options)
            self.ctrl.send_server_message(player_to_bid.player_id, msg)
        else:
            self.ctrl.serverchat("The bidding for this game is now over.")
            need_redeal = self.check_if_we_need_to_redeal()
            if need_redeal:
                self.collect_cards()
                self.cleanup_for_new_round()
                msg = self.ctrl.assemble_server_message("REDEAL", "no_message")
                self.ctrl.broadcast_server_message(msg)
                self.start_game()
            else:
                self.initiate_playing_of_cards()

    def get_remaining_bid_options(self):
        bids = self.trickbids[0]

        if "soloslim" in bids:
            options = "pass"
        elif "solo" in bids:
            options = "pass,soloslim"
        elif "misere_ouverte" in bids:
            options = "pass,soloslim,solo"
        elif "trull1" in bids:
            options = "pass"
            if self.settings["bid"]["soloslim_beats_trull"] == "True":
                options += ",soloslim"
            if self.settings["bid"]["solo_beats_trull"] == "True":
                options += ",solo"
            if self.settings["bid"]["misere_ouverte_beats_trull"] == "True":
                options += ",misere_ouverte"
        elif "abon12" in bids:
            options = "pass,soloslim,solo,misere_ouverte"
        elif "abon11" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12"
        elif "abon10" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11"
        elif "misere" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10"
        elif "abon9" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere"
        elif "join" in bids:
            options = (
                "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9"
            )
        elif "ask" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9,join"
        else:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9,ask"

        if "trull1" not in bids:
            if len(bids) == 4:
                if "ask" in bids and bids.count("pass") == 3:
                    # the person who asked can now go alone or decide to play a higher game
                    options = options.replace(",ask", "")
                    options = options.replace(",join", "")
                    options = options + ",alone"
                else:
                    options = None
        else:
            # when we have trull we already have 2 default bids in the trickbids
            if len(bids) == 6:
                options = None

        return options

    def check_if_we_need_to_redeal(self):
        bids = self.trickbids[0]
        redeal = False
        if bids.count("pass") == 4 and "ask" in bids:
            self.ctrl.serverchat(
                "One player asked, nobody joined, "
                "player did not go alone, next player will redeal."
            )
            self.dealer_seat = (self.dealer_seat + 1) % 4
            redeal = True
        elif bids.count("pass") == 4 and "ask" not in bids:
            self.ctrl.serverchat("Everyone passed, same dealer will redeal.")
            redeal = True
        return redeal

    def cleanup_for_new_round(self):
        """ cleans up the structures used for storing bids"""
        self.last_card_before_dealing = None
        self.seat_to_bid = (self.dealer_seat + 1) % 4
        self.trickbids = [list(), list(), list()]
        self.trick = list()
        self.trump = None
        self.type_of_game = None

    def divide_teams(self):
        self.attackers = list()
        self.defenders = list()

        bids = self.trickbids[0]
        trumps = self.trickbids[1]
        bidders = self.trickbids[2]

        self.player_to_play_card = self.seats[
            (self.dealer_seat + 1) % 4
        ]  # left from dealer is the standard choice

        if "soloslim" in bids:
            bidder = self.get_player_from_id(
                bidders[bids.index("soloslim")]
            )  # todo check this!!! THIS DOES NOT WORK!!!
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("soloslim")]
            if self.settings.getboolean("bid", "soloslim_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "soloslim"
        elif "solo" in bids:
            bidder = bidders[bids.index("solo")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("solo")]
            if self.trump == "no_trump":
                self.trump = None
            if self.settings.getboolean("bid", "solo_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "solo"
        elif "misere_ouverte" in bids:
            bidder = bidders[bids.index("misere_ouverte")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = None
            if self.settings.getboolean("bid", "misere_ouverte_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "misere_ouverte"
        elif "trull1" in bids:
            bidder = bidders[bids.index("trull1")]
            self.attackers.append(bidder)
            bidder = bidders[bids.index("trull2")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("trull2")]
            self.player_to_play_card = (
                bidder  # trull 2 player is the one who starts the round
            )
            self.type_of_game = "trull"
        elif "abon12" in bids:
            bidder = bidders[bids.index("abon12")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("abon12")]
            if self.settings.getboolean("bid", "abondance_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "abon12"
        elif "abon11" in bids:
            bidder = bidders[bids.index("abon11")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("abon11")]
            if self.settings.getboolean("bid", "abondance_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "abon11"
        elif "abon10" in bids:
            bidder = bidders[bids.index("abon10")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("abon10")]
            if self.settings.getboolean("bid", "abondance_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "abon10"
        elif "misere" in bids:
            bidder = bidders[bids.index("misere")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = None
            if self.settings.getboolean("bid", "misere_plays_first"):
                self.player_to_play_card = bidder
            self.type_of_game = "misere"
        elif "abon9" in bids:
            bidder = bidders[bids.index("abon9")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("abon9")]
            self.type_of_game = "abon9"
        elif "join" in bids:
            bidder = bidders[bids.index("join")]
            self.attackers.append(bidder)
            bidder = bidders[bids.index("ask")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("ask")]
            self.type_of_game = "together"
        elif "alone" in bids:
            bidder = bidders[bids.index("alone")]
            self.attackers.append(bidder)
            self.defenders = [
                player for player in self.seats if player not in self.attackers
            ]
            self.trump = trumps[bids.index("alone")]
            self.type_of_game = "alone"
        else:
            self.ctrl.serverchat("Impossible for the ctrl to divide the teams")

    def collect_cards(self):
        """
        collect cards from all hands starting with the person left from the dealer,
        as required in a redeal
        """
        for i in range(4):
            player = self.seats[(self.dealer_seat + 1 + i) % 4]
            self.deck = self.deck + player.hand
            player.hand = pd.Stack()

    def initiate_playing_of_cards(self):
        msg = self.ctrl.assemble_server_message("HIDETRUMP", "")
        self.ctrl.broadcast_server_message(msg)
        self.divide_teams()
        self.broadcast_trick_information()
        self.ask_to_play_card()

    def broadcast_trick_information(self):
        who_list = list()
        for player in self.attackers:
            who_list.append(player.name)
        who = ",".join(who_list)
        msg = who + " is/are playing a game of " + self.type_of_game
        if self.trump is not None:
            msg += " with " + self.trump + " for trump."
        else:
            msg += " without trump."
        self.ctrl.serverchat(msg)

    def ask_to_play_card(self):
        msg = self.ctrl.assemble_server_message("PLEASEPLAY", "")
        self.ctrl.send_server_message(self.player_to_play_card.player_id, msg)

    def process_played_card(self, player, abbrev):
        # todo verify
        self.ctrl.serverchat(player.name + " plays card " + abbrev)  # debug
        validated = self.validate_and_add_card_to_trick(player, abbrev)
        if not validated:
            self.ask_to_play_card()
        else:
            msg = self.ctrl.assemble_server_message(
                "CARD_WAS_PLAYED", "%s,%s" % (player.player_id, abbrev)
            )
            self.ctrl.broadcast_server_message(msg)

    def validate_and_add_card_to_trick(self, player, abbrev):
        """
        perform a series of checks on the played card to see if it is a valid card choice,
        abiding by all the rules
        """

        # check if the card is on the players hand
        player_has_card = False
        player_pd_card = None
        for card in player.hand:
            if card.abbrev == abbrev:
                player_has_card = True
                player_pd_card = card
                break
        if not player_has_card:
            return False

        # if it is trull and we are in the trull-8 mode than the first card must be the highest card of trump
        if (
            len(self.tricks) == 0
            and self.type_of_game == "trull"
            and self.settings["points"]["trulltricks"] == "8"
        ):
            highest_trump_card = self.get_highest_card_of_suit_in_stack(
                player.hand, self.trump
            )
            print(
                "we are in trull 8 mode, trump is %s, card  that player wants to play is %s and highest card "
                "on his hand is %s"
                % (self.trump, player_pd_card.abbrev, highest_trump_card.abbrev)
            )
            if player_pd_card is not highest_trump_card:
                print("card not validated player should have played higher")
                return False

        # check if the player has followed the suit if he was able to
        if len(self.trick) != 0:
            print("player has to follow suit if he can")
            if player_pd_card.suit != self.trick[0][0].suit:
                for card in player.hand:
                    if card.suit == self.trick[0].suit:
                        print("player should have followed suit")
                        return False

        self.trick.append([player, player_pd_card])
        return True

    def get_highest_card_of_suit_in_stack(self, stack, suit):
        """
        returns the highest card of a given suit in a given stack
        """
        seq = list()
        for card in stack:
            v = 0

            if card.suit == suit:
                v += 100

            if card.value == "Jack":
                v += 11
            elif card.value == "Queen":
                v += 12
            elif card.value == "King":
                v += 13
            elif card.value == "Ace":
                v += 14
            else:
                v += int(card.value)  # 2 - 10

            seq.append(v)
        position = seq.index(max(seq))
        return stack[position]
