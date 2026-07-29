"""Pure rules engine for Vlaamse wies.

This package contains no I/O, no async, no Qt and no timers: every function is
synchronous and deterministic given an injected RNG. That is what makes the
rules unit-testable, replayable, and cheap for a future AI player to simulate.
``tests/core/test_purity.py`` enforces it.
"""

from jwies_core.cards import Card, Rank, Suit
from jwies_core.seats import ALL_SEATS, Seat
from jwies_core.trick import PlayedCard, legal_moves, trick_winner

__all__ = [
    "ALL_SEATS",
    "Card",
    "PlayedCard",
    "Rank",
    "Seat",
    "Suit",
    "legal_moves",
    "trick_winner",
]
