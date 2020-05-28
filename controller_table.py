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
        cnt = len(self.trickbids[0])
        if cnt < 4:
            return (self.seats[self.seat_to_bid])
        elif cnt == 4:
            opts = self.get_remaining_bid_options()
            if opts is None:
                return (None)
            else:
                return (self.seats[self.seat_to_bid])
        else:
            return (None)

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
        self.trickbids[0].append(action)  # what type of bid was made?
        self.trickbids[1].append(suit)  # if a specific suit was given, log it
        self.trickbids[2].append(self.seats[self.seat_to_bid])  # who made the bid
        self.seat_to_bid = (self.seat_to_bid + 1) % 4

    def divide_teams(self):
        self.attackers = list()
        self.defenders = list()

        i = 0
        if "misere" in self.trickbids[0]:
            bidder = self.trickbids[2][self.trickbids[0].index("misere")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = None
        elif "abondance" in self.trickbids[0]:
            bidder = self.trickbids[2][self.trickbids[0].index("abondance")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = self.trickbids[1][self.trickbids[0].index("abondance")]
        elif "join" in self.trickbids[0]:
            bidder = self.trickbids[2][self.trickbids[0].index("join")]
            self.attackers.append(bidder)
            bidder = self.trickbids[2][self.trickbids[0].index("ask")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = self.trickbids[1][self.trickbids[0].index("ask")]
        elif "alone" in self.trickbids[0]:
            bidder = self.trickbids[2][self.trickbids[0].index("ask")]
            self.attackers.append(bidder)
            self.defenders = [player for player in self.seats if player not in self.attackers]
            self.trump = self.trickbids[1][self.trickbids[0].index("alone")]
        elif "ask" in self.trickbids[0]:
            # a player asked, nobody joined, and finally he did not go alone, we should redeal and let
            # the next player redeal
            pass
        else:
            # everyone just passed, we should redeal
            pass
