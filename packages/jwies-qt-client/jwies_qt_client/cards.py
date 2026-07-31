"""Card codes to SVG element ids.

The client deliberately does not depend on ``jwies-core``: it only needs to
turn a wire code like ``"10S"`` into the element id ``"10_spade"`` used by
svg-cards.svg. Keeping this table here means the client carries no rules
engine, which is also why it can never disagree with the server about them.
"""

from __future__ import annotations

from typing import Final

__all__ = ["CARD_BACK", "card_label", "suit_label", "svg_element_id"]

CARD_BACK: Final = "back"

_SUIT_SVG: Final = {"C": "club", "D": "diamond", "H": "heart", "S": "spade"}
_RANK_SVG: Final = {
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "10": "10",
    "J": "jack",
    "Q": "queen",
    "K": "king",
    "A": "1",
}

_SUIT_NL: Final = {"C": "klaveren", "D": "koeken", "H": "harten", "S": "schoppen"}
_RANK_NL: Final = {
    "2": "twee",
    "3": "drie",
    "4": "vier",
    "5": "vijf",
    "6": "zes",
    "7": "zeven",
    "8": "acht",
    "9": "negen",
    "10": "tien",
    "J": "boer",
    "Q": "dame",
    "K": "heer",
    "A": "aas",
}


def svg_element_id(code: str) -> str:
    """``"10S"`` -> ``"10_spade"``. Returns ``"back"`` unchanged."""
    if code == CARD_BACK:
        return CARD_BACK
    rank, suit = code[:-1], code[-1]
    return f"{_RANK_SVG[rank]}_{_SUIT_SVG[suit]}"


def card_label(code: str) -> str:
    """A Dutch name for a card, used as an accessible label."""
    if code == CARD_BACK:
        return "gedekte kaart"
    rank, suit = code[:-1], code[-1]
    return f"{_SUIT_NL[suit]} {_RANK_NL[rank]}"


def suit_label(suit: str | None) -> str:
    return _SUIT_NL.get(suit or "", "zonder troef")
