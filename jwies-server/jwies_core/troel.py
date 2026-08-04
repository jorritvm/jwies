"""Troel (troela) detection.

Holding three or more aces forces a troel: that player and the holder of the
fourth ace play together, and the fourth ace's suit is trump. With several
single-ace holders, the partner is the first single-ace holder clockwise from
the troel player.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jwies_core.cards import Card, Rank, Suit
from jwies_core.seats import Seat, seat_order_from

__all__ = ["TroelResult", "detect_troel"]

TROEL_ACE_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class TroelResult:
    """Who plays the troel, with whom, and in which trump."""

    lead: Seat
    partner: Seat
    trump: Suit


def _aces(hand: Sequence[Card]) -> list[Card]:
    return [card for card in hand if card.rank is Rank.ACE]


def detect_troel(hands: Mapping[Seat, Sequence[Card]]) -> TroelResult | None:
    """Return the troel pairing, or ``None`` when no player holds 3+ aces."""
    lead: Seat | None = None
    for seat, hand in hands.items():
        if len(_aces(hand)) >= TROEL_ACE_THRESHOLD:
            lead = seat
            break
    if lead is None:
        return None

    # Look for the fourth ace, starting left of the troel player so the result
    # does not depend on dictionary ordering.
    for seat in seat_order_from(lead)[1:]:
        aces = _aces(hands[seat])
        if len(aces) == 1:
            return TroelResult(lead=lead, partner=seat, trump=aces[0].suit)

    # The troel player holds all four aces: hearts becomes trump and the
    # partner is whoever holds the king of hearts, else the queen of hearts.
    king = Card(Rank.KING, Suit.HEARTS)
    queen = Card(Rank.QUEEN, Suit.HEARTS)
    for wanted in (king, queen):
        for seat in seat_order_from(lead)[1:]:
            if wanted in hands[seat]:
                return TroelResult(lead=lead, partner=seat, trump=Suit.HEARTS)

    # Only reachable if the troel player also holds both the KH and QH.
    partner = seat_order_from(lead)[1]
    return TroelResult(lead=lead, partner=partner, trump=Suit.HEARTS)
