"""Pure rules engine for Vlaamse wies.

Every function is synchronous and deterministic given an injected RNG, which
makes the rules unit-testable, replayable, and cheap for a future AI player to
simulate. ``tests/core/test_purity.py`` enforces it.
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
