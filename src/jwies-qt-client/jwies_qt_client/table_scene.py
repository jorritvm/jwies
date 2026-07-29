"""Draws the table from server state.

The client holds no game logic whatsoever: it renders whatever the last
snapshot said and animates the events that follow. Which cards are playable,
whose turn it is, who is on which team - all of that arrives from the server.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsTextItem

from jwies_qt_client.cards import CARD_BACK, card_label, suit_label
from jwies_qt_client.layout import (
    CARD_ROTATE,
    CARDSCALE,
    NAME_COLOR_DEFAULT,
    SCENE_RECT_X,
    SCENE_RECT_Y,
    TEAM_COLOR_ATTACKERS,
    TEAM_COLOR_DEFENDERS,
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
    direction_of,
)
from jwies_qt_client.widgets import CardSignals, GraphicCard

__all__ = ["TableScene"]

CARDS_PER_HAND = 13


class TableScene(QGraphicsScene):
    """The green baize plus everything on it."""

    def __init__(self, renderer: QSvgRenderer, signals: CardSignals) -> None:
        super().__init__(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.setBackgroundBrush(QBrush(QColor("darkGreen")))
        self.renderer = renderer
        self.signals = signals
        self.field = self.addRect(0, 0, SCENE_RECT_X, SCENE_RECT_Y)
        self.field.setPen(QColor("darkGreen"))

        self.own_hand: list[GraphicCard] = []
        self.selected_card: str | None = None
        self._items: list[Any] = []

        self.trick_counter = QGraphicsTextItem("")
        self.trick_counter.setDefaultTextColor(QColor("white"))
        self.trick_counter.setFont(QFont("Sans", 11))
        self.trick_counter.setPos(10, 10)
        self.addItem(self.trick_counter)

    # --- helpers -----------------------------------------------------------

    def _clear_dynamic(self) -> None:
        for item in self._items:
            if item.scene() is self:
                self.removeItem(item)
        self._items.clear()
        self.own_hand.clear()

    def _add(self, item: Any) -> Any:
        self.addItem(item)
        self._items.append(item)
        return item

    def _card(self, code: str, z: int, hand: list[GraphicCard] | None = None) -> GraphicCard:
        card = GraphicCard(code, z, self.renderer, hand, self.signals)
        card.setScale(CARDSCALE)
        card.setToolTip(card_label(code))
        return card

    # --- rendering ---------------------------------------------------------

    def render_snapshot(self, state: dict[str, Any]) -> None:
        """Redraw everything from the current client state."""
        self._clear_dynamic()

        your_seat = state.get("your_seat")
        seats = state.get("seats") or []
        contract = state.get("contract")
        trick = state.get("trick") or []
        if state.get("show_last_trick") and state.get("last_trick"):
            trick = state["last_trick"]

        played_seats = {entry["seat"] for entry in trick}
        tricks_done = (state.get("trick_counts") or {}).get("declarers", 0) + (
            state.get("trick_counts") or {}
        ).get("defenders", 0)

        for seat in seats:
            index = seat["seat"]
            direction = direction_of(index, your_seat)
            self._draw_name(seat, direction, state, contract)

            if direction == "SOUTH":
                self._draw_own_hand(state)
            else:
                open_hand = (state.get("open_hands") or {}).get(str(index)) or (
                    state.get("open_hands") or {}
                ).get(index)
                if open_hand:
                    self._draw_face_up(open_hand, direction)
                else:
                    remaining = max(
                        0, CARDS_PER_HAND - tricks_done - (1 if index in played_seats else 0)
                    )
                    self._draw_backs(remaining, direction)

        self._draw_trick(trick, your_seat)
        self._draw_trump(state, your_seat)
        self._draw_counter(state, contract)

    def _draw_name(
        self,
        seat: dict[str, Any],
        direction: str,
        state: dict[str, Any],
        contract: dict[str, Any] | None,
    ) -> None:
        username = seat.get("username")
        if not username:
            return
        text = username
        if seat.get("is_dealer"):
            text += " (deler)"
        if not seat.get("connected"):
            text += " (offline)"

        label = QGraphicsTextItem(text)
        colour = NAME_COLOR_DEFAULT
        if contract:
            colour = (
                TEAM_COLOR_ATTACKERS
                if seat["seat"] in contract["declarers"]
                else TEAM_COLOR_DEFENDERS
            )
        label.setDefaultTextColor(QColor(colour))
        font = QFont("Sans", 10)
        font.setBold(state.get("pending_seat") == seat["seat"])
        label.setFont(font)
        label.setPos(X_NAME[direction], Y_NAME[direction])
        label.setZValue(50)
        self._add(label)

    def _draw_own_hand(self, state: dict[str, Any]) -> None:
        hand = state.get("hand") or []
        prompt = state.get("prompt") or {}
        playable = set(prompt.get("legal_cards", []) if prompt.get("kind") == "play" else [])
        turned = state.get("turned_trump")

        for index, code in enumerate(hand):
            card = self._card(code, 10 + index, self.own_hand)
            card.is_playable = code in playable
            card.is_trump_shown = bool(turned) and code == turned
            card.setPos(
                X_CARD["SOUTH"] + index * XINC_CARD["SOUTH"],
                card.base_y() - (0 if code != self.selected_card else 40),
            )
            if code in playable:
                card.setOpacity(1.0)
            elif playable:
                card.setOpacity(0.55)
            self.own_hand.append(card)
            self._add(card)

    def _draw_backs(self, count: int, direction: str) -> None:
        for index in range(count):
            card = self._card(CARD_BACK, index)
            card.setRotation(CARD_ROTATE[direction])
            card.setPos(
                X_CARD[direction] + index * XINC_CARD[direction],
                Y_CARD[direction] + index * YINC_CARD[direction],
            )
            self._add(card)

    def _draw_face_up(self, codes: list[str], direction: str) -> None:
        for index, code in enumerate(codes):
            card = self._card(code, index)
            card.setRotation(CARD_ROTATE[direction])
            card.setPos(
                X_CARD[direction] + index * XINC_CARD[direction],
                Y_CARD[direction] + index * YINC_CARD[direction],
            )
            self._add(card)

    def _draw_trick(self, trick: list[dict[str, Any]], your_seat: int | None) -> None:
        for position, entry in enumerate(trick):
            direction = direction_of(entry["seat"], your_seat)
            card = self._card(entry["card"], 10000 + position)
            card.setRotation(CARD_ROTATE[direction])
            card.setPos(X_PLAYED_CARD[direction], Y_PLAYED_CARD[direction])
            self._add(card)

    def _draw_trump(self, state: dict[str, Any], your_seat: int | None) -> None:
        turned = state.get("turned_trump")
        if not turned:
            return
        dealer_seat = state.get("dealer_seat")
        if dealer_seat is None:
            return
        direction = direction_of(dealer_seat, your_seat)
        if direction == "SOUTH":
            # Your own trump card is lifted out of your hand rather than drawn
            # a second time, which is how the pre-refactor client showed it.
            for card in self.own_hand:
                if card.code == turned:
                    card.is_trump_shown = True
                    card.setY(card.base_y())
            return
        card = self._card(turned, 0)
        card.setRotation(CARD_ROTATE[direction])
        card.setPos(X_TRUMPCARD[direction], Y_TRUMPCARD[direction] - TRUMP_ELEVATION)
        self._add(card)

    def _draw_counter(self, state: dict[str, Any], contract: dict[str, Any] | None) -> None:
        if not contract:
            self.trick_counter.setPlainText("")
            return
        counts = state.get("trick_counts") or {}
        trump = suit_label(contract.get("trump"))
        self.trick_counter.setPlainText(
            f"Aanval: {counts.get('declarers', 0)}\n"
            f"Verdediging: {counts.get('defenders', 0)}\n"
            f"Troef: {trump}"
        )
