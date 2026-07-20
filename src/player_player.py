import pydealer as pd
from PyQt6.QtGui import QColor, QTransform
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QGraphicsScene

from constants import (
    CARDSCALE,
    CARD_ROTATE,
    NAME_COLOR_DEFAULT,
    SELECT_ELEVATION,
    TRUMP_ELEVATION,
    X_CARD,
    X_NAME,
    X_PLAYED_CARD,
    X_TRUMPCARD,
    XINC_CARD,
    Y_CARD,
    Y_NAME,
    Y_PLAYED_CARD,
    Y_TRUMPCARD,
    YINC_CARD,
)
from player_helper_classes import GraphicCard
from player_helper_functions import sort_pdstack_on_hand


class Player:
    def __init__(
        self,
        player_id: int | str,
        name: str,
        seat: str,
        scene: QGraphicsScene,
        svgrenderer: QSvgRenderer,
    ) -> None:
        self.player_id = int(player_id)  # this is the id the server has for the player
        self.name = name
        self.seat = seat  # this is the seat relative to where you are sitting (south)
        self.scene = scene
        self.svgrenderer = svgrenderer
        self.hand: list[GraphicCard] = []  # list of GraphicCard objects

        self.is_dealer = False
        self.trumpcard: GraphicCard | None = None
        self.team_color: str | None = None  # color of the team this player belongs to

        self.setup_default_cards()
        self.name_label = None
        self.draw_name()
        self.draw_hand()

    def setup_default_cards(self) -> None:
        for z in range(13):
            card = GraphicCard("back", z + 10, self.svgrenderer, self.hand)
            self.hand.append(card)

    def restore_default_cards(self) -> None:
        if len(self.hand) == 0:
            self.setup_default_cards()
            self.draw_hand()

    def draw_name(self) -> None:
        name = self.name
        if self.is_dealer:
            name = "Dealer: " + name
        self.name_label = self.scene.addText(name)
        self.name_label.setDefaultTextColor(
            QColor(self.team_color if self.team_color is not None else NAME_COLOR_DEFAULT)
        )
        self.name_label.setX(X_NAME[self.seat])
        self.name_label.setY(Y_NAME[self.seat])

    def redraw_name(self) -> None:
        if self.name_label is not None:
            self.scene.removeItem(self.name_label)
        self.draw_name()

    def set_dealer(self, is_dealer: bool) -> None:
        self.is_dealer = is_dealer
        self.redraw_name()

    def set_team_color(self, color: str | None) -> None:
        """color the name of this player in his team's color, or None to reset it"""
        self.team_color = color
        self.redraw_name()

    def receive_cards(self, card_abbreviation_list: list[str]) -> None:
        # delete the backside up cards first
        for card in self.hand:
            self.scene.removeItem(card)

        self.hand = []

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

    def amount_of_aces_on_hand(self) -> int:
        # if i have three aces i let people know it is trull
        aces = 0
        for card in self.hand:
            if card.value == "Ace":
                aces += 1
        return aces

    def draw_hand(self) -> None:
        seat = self.seat
        for card in self.hand:
            transformation = QTransform()
            transformation.scale(CARDSCALE, CARDSCALE)
            card.setX(X_CARD[seat] + (card.z - 10) * XINC_CARD[seat])
            card.setY(Y_CARD[seat] + (card.z - 10) * YINC_CARD[seat])
            transformation.rotate(CARD_ROTATE[seat])
            card.setTransform(transformation)
            self.scene.addItem(card)

    def draw_trump_card(self, abbrev: str) -> None:
        if self.seat == "SOUTH":
            # we are the dealer ourselves: the trump card is already face up in our
            # hand, so elevate that card instead of drawing a duplicate copy
            for card in self.hand:
                if card.abbrev == abbrev:
                    card.is_trump_shown = True
                    card.setY(
                        card.base_y()
                        - (SELECT_ELEVATION if card.is_selected else 0)
                    )
                    self.trumpcard = card
                    break
        else:
            # another player deals: his cards are face down, so show the trump
            # card face up on top of his hand
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

    def hide_trump_card(self) -> None:
        if self.trumpcard is not None:
            if self.trumpcard.is_trump_shown:
                # own hand card: lower it back into the hand instead of removing it
                self.trumpcard.is_trump_shown = False
                self.trumpcard.setY(
                    self.trumpcard.base_y()
                    - (SELECT_ELEVATION if self.trumpcard.is_selected else 0)
                )
            else:
                self.scene.removeItem(self.trumpcard)
        self.trumpcard = None

    def draw_played_card(self, abbrev: str, tricksize: str) -> None:
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

    def reset(self) -> None:
        for card in self.hand:
            self.scene.removeItem(card)
        self.hand = []  # list of GraphicCard objects
        self.setup_default_cards()
        self.draw_hand()
        self.set_dealer(False)
        self.hide_trump_card()
