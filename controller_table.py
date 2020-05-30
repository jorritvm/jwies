import pydealer as pd
import random


class Player:

    def __init__(self, id):
        self.id = id
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


class Table:

    def __init__(self):
        self.seats = list()  # a list of player instances
        self.dealer_seat = 0

        # create a shuffled deck of 52 cards
        self.deck = pd.Deck()
        self.deck.shuffle()

        # trick info
        self.last_card_before_dealing = None
        self.seat_to_bid = (self.dealer_seat + 1) % 4  # player left from dealer starts to bid
        self.trickbids = [list(), list(), list()]  # list 1: bid action, list 2: trump, list 3: who made the bid
        self.trick = pd.Stack()
        self.tricknumber = 0

        # two teams
        self.attackers = list()
        self.defenders = list()
        self.trump = None

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
        return returnstr

    def cut_deck(self, num):
        self.deck = pd.stack.Stack(cards=self.deck[num:52] + self.deck[0:num])

    def divide_cards(self, roundsize):
        self.last_card_before_dealing = self.deck[51]
        for cards_to_deal_this_round in roundsize:
            for i in range(4):
                self.seats[(self.dealer_seat + i + 1) % 4].hand.add(self.deck.deal(cards_to_deal_this_round))

    def get_dealer(self):
        return self.seats[self.dealer_seat]

    def check_for_trull(self):
        trull = False
        for player in self.seats:
            if player.amount_of_aces_on_hand() >= 3:
                trull = True
        return trull

    def get_player_to_bid(self):
        """ the next player to bid is simply the one to the left, and, if one asked, and three passed
        he who asked has a final say"""
        bids = self.trickbids[0]
        if len(bids) < 4:
            return self.seats[self.seat_to_bid]
        elif len(bids) == 4:
            if "ask" in bids and bids.count("pass") == 3:
                return self.trickbids[2][bids.index("ask")]
            else:
                return None
        else:
            return None

    def get_remaining_bid_options(self):
        bids = self.trickbids[0]

        if "soloslim" in bids:
            options = "pass"
        elif "solo" in bids:
            options = "pass,soloslim"
        elif "misere_ouverte" in bids:
            options = "pass,soloslim,solo"
        elif "trull" in bids:
            options = "pass,soloslim,solo,misere_ouverte"
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
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9"
        elif "ask" in bids:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9,join"
        else:
            options = "pass,soloslim,solo,misere_ouverte,abon12,abon11,abon10,misere,abon9,ask"

        if len(bids) == 4:
            if "ask" in bids and bids.count("pass") == 3:
                # the person who asked can now go alone or decide to play a higher game
                options = options.replace(",ask","")
                options = options.replace(",join", "")
                options = options + ",alone"
            else:
                options = None

        return options

    def add_bid(self, newbid):
        action = newbid[0]
        suit = newbid[1]
        player = newbid[2]
        # even if a player already bid, and has to do a final bid, we append it! (so trickbids > 4)
        self.trickbids[0].append(action)  # what type of bid was made?
        self.trickbids[1].append(suit)  # if a specific suit was given, log it
        self.trickbids[2].append(player)  # who made the bid
        self.seat_to_bid = (self.seat_to_bid + 1) % 4

    def divide_teams(self):
        self.attackers = list()
        self.defenders = list()

        bids =  self.trickbids[0]
        trumps = self.trickbids[1]
        bidders = self.trickbids[2]

        self.ready_to_start_game = True

        i = 0
        if "soloslim" in bids:
            bidder = bidders[bids.index("soloslim")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("soloslim")]
            if self.trump == "no_trump":
                self.trump = None
            self.player_to_play_card = bidder
        elif "solo" in bids:
            bidder = bidders[bids.index("solo")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("solo")]
        if "misere_ouverte" in bids:
            bidder = bidders[bids.index("misere_ouverte")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = None
        elif "abon12" in bids:
            bidder = bidders[bids.index("abon12")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("abon12")]
        elif "abon11" in bids:
            bidder = bidders[bids.index("abon11")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("abon11")]
        elif "abon10" in bids:
            bidder = bidders[bids.index("abon10")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("abon10")]
        elif "misere" in bids:
            bidder = bidders[bids.index("misere")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = None
        elif "abon9" in bids:
            bidder = bidders[bids.index("abon9")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("abon9")]
        elif "join" in bids:
            bidder = bidders[bids.index("join")]
            self.attackers.append(bidder)
            bidder = bidders[bids.index("ask")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("ask")]
        elif "alone" in bids:
            bidder = bidders[bids.index("alone")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = trumps[bids.index("alone")]
        elif bids.count("pass") == 4 & "ask" in bids:
            # a player asked, nobody joined, and finally he did not go alone, the next player should redeal
            self.serverchat("One player asked, nobody joined, player did not go alone, next player will redeal.")
            self.ready_to_start_game = False
            # NEWROUND
            pass
        else:
            # everyone just passed, same dealer should redeal
            self.serverchat("Everyone passed, same dealer will redeal.")
            # NEWROUND
            self.ready_to_start_game = False
            pass

    def get_player_to_play_card(self):
        pass