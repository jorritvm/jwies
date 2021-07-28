from PyQt5.QtGui import *
import pydealer as pd

from staticvar import *
from player_helper_functions import *
from player_helper_classes import *

class Player:
    def __init__(self, player_id, name, seat, scene, svgrenderer):
        self.player_id = int(player_id)  # this is the id the server has for the player
        self.name = name
        self.seat = seat  # this is the seat relative to where you are sitting (south)
        self.scene = scene
        self.svgrenderer = svgrenderer
        self.hand = list()  # list of GraphicCard objects

        self.setup_default_cards()
        self.name_label = None
        self.draw_name(seat, name)
        self.draw_hand()

        self.is_dealer = False
        self.trumpcard = None

    def setup_default_cards(self):
        for z in range(13):
            card = GraphicCard("back", z + 10, self.svgrenderer, self.hand)
            self.hand.append(card)

    def restore_default_cards(self):
        if len(self.hand) == 0:
            self.setup_default_cards()
            self.draw_hand()

    def draw_name(self, seat, name):
        self.name_label = self.scene.addText(name)
        self.name_label.setX(X_NAME[seat])
        self.name_label.setY(Y_NAME[seat])

    def set_dealer(self, is_dealer):
        self.is_dealer = is_dealer
        self.scene.removeItem(self.name_label)
        if is_dealer:
            name = "Dealer: " + self.name
        else:
            name = self.name
        self.draw_name(self.seat, name)

    def receive_cards(self, card_abbreviation_list):
        # delete the backside up cards first
        for card in self.hand:
            self.scene.removeItem(card)

        self.hand = list()

        # sort the received cards and put them on my hand
        deck = pd.deck.Deck()
        stack = pd.stack.Stack(cards=deck.get_list(card_abbreviation_list))
        stack = sort_pdstack_on_hand(stack)
        z = 10
        for pdcard in stack:
            card = GraphicCard(pdcard.abbrev, z, self.svgrenderer, self.hand)
            self.hand.append(card)
            z += 1

        # draw them on the board
        self.draw_hand()

    def amount_of_aces_on_hand(self):
        # if i have three aces i let people know it is trull
        aces = 0
        for card in self.hand:
            if card.value == "Ace":
                aces += 1
        return aces

    def draw_hand(self):
        seat = self.seat
        for card in self.hand:
            transformation = QTransform()
            transformation.scale(CARDSCALE, CARDSCALE)
            card.setX(X_CARD[seat] + (card.z - 10) * XINC_CARD[seat])
            card.setY(Y_CARD[seat] + (card.z - 10) * YINC_CARD[seat])
            transformation.rotate(CARD_ROTATE[seat])
            card.setTransform(transformation)
            self.scene.addItem(card)

    def draw_trump_card(self, abbrev):
        card = GraphicCard(abbrev, 0, self.svgrenderer, self.hand)
        transformation = QTransform()
        transformation.scale(CARDSCALE, CARDSCALE)
        card.setX(X_TRUMPCARD[self.seat])
        card.setY(Y_TRUMPCARD[self.seat])
        transformation.rotate(CARD_ROTATE[self.seat])
        card.setTransform(transformation)
        self.scene.addItem(card)
        self.trumpcard = card
        self.is_dealer = True

    def hide_trump_card(self):
        self.scene.removeItem(self.trumpcard)
        self.trumpcard = None

    def draw_played_card(self, abbrev, tricksize):
        # create the card with the proper Z-level & draw it
        card = GraphicCard(abbrev, 10000 + int(tricksize), self.svgrenderer, self.hand)
        transformation = QTransform()
        transformation.scale(CARDSCALE, CARDSCALE)
        card.setX(X_PLAYED_CARD[self.seat])
        card.setY(Y_PLAYED_CARD[self.seat])
        transformation.rotate(CARD_ROTATE[self.seat])
        card.setTransform(transformation)
        self.scene.addItem(card)

        # remove a card from the hand of the player
        if self.seat == "SOUTH":
            # the correct card when looking at our own hand
            for card in self.hand:
                if card.abbrev == abbrev:
                    self.hand.remove(card)
                    self.scene.removeItem(card)
        else:
            # pop off the last drawn card for another player
            last_card_item = self.hand.pop()
            self.scene.removeItem(last_card_item)

    def reset(self):
        for card in self.hand:
            self.scene.removeItem(card)
        self.hand = list()  # list of GraphicCard objects
        self.setup_default_cards()
        self.draw_hand()
        self.set_dealer(False)
        self.scene.removeItem(self.trumpcard)
        self.trumpcard = None



