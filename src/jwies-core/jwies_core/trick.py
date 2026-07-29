"""Trick rules: which cards may be played, and who wins.

The central design decision of the refactor lives here. The old code had
``validate_and_add_card_to_trick``, which judged a card after the fact. This
module instead *computes the legal set*: validation becomes
``card in legal_moves(...)``, prompts can ship the legal set to the client, and
an AI never has to reimplement follow-suit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from jwies_core.cards import Card, Suit, highest_of_suit
from jwies_core.seats import Seat

__all__ = ["PlayedCard", "lead_suit", "legal_moves", "trick_winner"]


@dataclass(frozen=True, slots=True)
class PlayedCard:
    """A card on the table, together with who played it."""

    seat: Seat
    card: Card


def lead_suit(trick: Sequence[PlayedCard]) -> Suit | None:
    """The suit that was led, or ``None`` when the trick is still empty."""
    return trick[0].card.suit if trick else None


def legal_moves(
    hand: Sequence[Card],
    trick: Sequence[PlayedCard],
    trump: Suit | None,
    *,
    must_lead_highest_trump: bool = False,
) -> list[Card]:
    """Every card in ``hand`` that may legally be played right now.

    ``must_lead_highest_trump`` covers the troel-8 opening lead. When the
    leader holds no trump at all the obligation cannot be met and simply does
    not apply, rather than silently degrading to "your highest card overall" as
    the old ``get_highest_card_of_suit_in_stack`` did.
    """
    if not hand:
        return []

    led = lead_suit(trick)

    if led is None:
        if must_lead_highest_trump and trump is not None:
            highest = highest_of_suit(hand, trump)
            if highest is not None:
                return [highest]
        return list(hand)

    following = [card for card in hand if card.suit is led]
    return following if following else list(hand)


def trick_winner(trick: Sequence[PlayedCard], trump: Suit | None) -> Seat:
    """The seat that takes the trick.

    Keeps the exact semantics of the old ``Table.find_out_who_won``: trump
    beats the led suit, the led suit beats a discard, and rank decides within a
    suit. Expressed as a sort key instead of the old +200/+100 score arithmetic.
    """
    if not trick:
        raise ValueError("een lege slag heeft geen winnaar")

    led = lead_suit(trick)

    def strength(played: PlayedCard) -> tuple[bool, bool, int]:
        card = played.card
        return (card.suit is trump, card.suit is led, int(card.rank))

    return max(trick, key=strength).seat
