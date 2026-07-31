"""Card model.

Replaces the ``pydealer`` dependency (unmaintained since 2015). The card code
(``"AH"``, ``"10S"``, ``"QD"``) is kept identical to pydealer's ``abbrev``
because it doubles as the JSON representation of a card on the wire.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Final

__all__ = [
    "CARDS_PER_HAND",
    "DECK_SIZE",
    "Card",
    "Rank",
    "Suit",
    "full_deck",
    "highest_of_suit",
    "shuffled_deck",
    "sort_for_hand",
]

DECK_SIZE: Final = 52
CARDS_PER_HAND: Final = 13


class Suit(StrEnum):
    """The four suits. The value is the single letter used in a card code."""

    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"

    @property
    def svg_name(self) -> str:
        """Singular suit name as used in the SVG-cards element ids."""
        return _SUIT_SVG_NAME[self]


class Rank(IntEnum):
    """Card ranks, ordered by trick-taking strength."""

    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def code(self) -> str:
        """The rank part of a card code: ``"2"``..``"10"``, ``"J"``, ``"Q"``, ``"K"``, ``"A"``."""
        return _RANK_CODE[self]

    @property
    def svg_name(self) -> str:
        """Rank as used in the SVG-cards element ids (the ace is ``"1"``)."""
        return _RANK_SVG_NAME[self]


_SUIT_SVG_NAME: Final[dict[Suit, str]] = {
    Suit.CLUBS: "club",
    Suit.DIAMONDS: "diamond",
    Suit.HEARTS: "heart",
    Suit.SPADES: "spade",
}

_RANK_CODE: Final[dict[Rank, str]] = {
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
    **{rank: str(int(rank)) for rank in Rank if rank <= Rank.TEN},
}

_RANK_SVG_NAME: Final[dict[Rank, str]] = {
    **{rank: str(int(rank)) for rank in Rank if rank <= Rank.TEN},
    Rank.JACK: "jack",
    Rank.QUEEN: "queen",
    Rank.KING: "king",
    Rank.ACE: "1",
}

_CODE_TO_RANK: Final[dict[str, Rank]] = {rank.code: rank for rank in Rank}

# Suit ordering used when fanning a hand out on screen. Ported verbatim from
# player_helper_functions.sort_pdstack_on_hand so hands keep looking familiar.
_HAND_SORT_ORDER: Final[dict[Suit, int]] = {
    Suit.CLUBS: 0,
    Suit.DIAMONDS: 1,
    Suit.SPADES: 2,
    Suit.HEARTS: 3,
}


@dataclass(frozen=True, slots=True, order=False)
class Card:
    """A single playing card. Immutable and hashable."""

    rank: Rank
    suit: Suit

    @property
    def code(self) -> str:
        """Wire representation, e.g. ``"AH"``, ``"10S"``, ``"QD"``."""
        return f"{self.rank.code}{self.suit.value}"

    @property
    def svg_element_id(self) -> str:
        """Element id in svg-cards.svg, e.g. ``"1_heart"``, ``"10_spade"``."""
        return f"{self.rank.svg_name}_{self.suit.svg_name}"

    @classmethod
    def from_code(cls, code: str) -> Card:
        """Parse a wire card code. Raises ``ValueError`` on anything unexpected."""
        if len(code) < 2:
            raise ValueError(f"ongeldige kaartcode: {code!r}")
        rank_part, suit_part = code[:-1], code[-1]
        try:
            suit = Suit(suit_part)
        except ValueError:
            raise ValueError(f"ongeldige kleur in kaartcode: {code!r}") from None
        rank = _CODE_TO_RANK.get(rank_part)
        if rank is None:
            raise ValueError(f"ongeldige waarde in kaartcode: {code!r}")
        return cls(rank=rank, suit=suit)

    def __str__(self) -> str:
        return self.code


def full_deck() -> list[Card]:
    """All 52 cards in a fixed, reproducible order."""
    return [Card(rank=rank, suit=suit) for suit in Suit for rank in Rank]


def shuffled_deck(rng: random.Random) -> list[Card]:
    """A full deck shuffled with the supplied RNG (injected for reproducibility)."""
    deck = full_deck()
    rng.shuffle(deck)
    return deck


def sort_for_hand(cards: Iterable[Card]) -> list[Card]:
    """Sort cards the way a player fans them out: by suit group, then by rank."""
    return sorted(cards, key=lambda card: (_HAND_SORT_ORDER[card.suit], card.rank))


def highest_of_suit(cards: Sequence[Card], suit: Suit) -> Card | None:
    """Highest card of ``suit`` in ``cards``, or ``None`` if the suit is absent.

    The old implementation (``Table.get_highest_card_of_suit_in_stack``) fell
    back to the globally highest card when the player held none of the suit,
    which silently produced wrong answers. Returning ``None`` forces the caller
    to make that decision explicitly.
    """
    matching = [card for card in cards if card.suit is suit]
    return max(matching, key=lambda card: card.rank) if matching else None
