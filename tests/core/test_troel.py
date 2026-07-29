"""Troel detection and partner selection."""

from __future__ import annotations

from jwies_core.cards import Card, Rank, Suit
from jwies_core.seats import ALL_SEATS, Seat
from jwies_core.troel import detect_troel

ACE_C = Card(Rank.ACE, Suit.CLUBS)
ACE_D = Card(Rank.ACE, Suit.DIAMONDS)
ACE_H = Card(Rank.ACE, Suit.HEARTS)
ACE_S = Card(Rank.ACE, Suit.SPADES)
KING_H = Card(Rank.KING, Suit.HEARTS)
QUEEN_H = Card(Rank.QUEEN, Suit.HEARTS)
FILLER = Card(Rank.TWO, Suit.CLUBS)


def hands(**by_seat: list[Card]) -> dict[Seat, list[Card]]:
    table = {seat: [FILLER] for seat in ALL_SEATS}
    for name, cards in by_seat.items():
        table[Seat(int(name[1:]))] = cards
    return table


def test_no_troel_without_three_aces() -> None:
    assert detect_troel(hands(s0=[ACE_C, ACE_D], s1=[ACE_H], s2=[ACE_S])) is None


def test_three_aces_forces_a_troel_with_the_fourth_ace_holder() -> None:
    result = detect_troel(hands(s0=[ACE_C, ACE_D, ACE_H], s2=[ACE_S]))
    assert result is not None
    assert result.lead == Seat(0)
    assert result.partner == Seat(2)
    assert result.trump is Suit.SPADES


def test_partner_is_the_first_single_ace_holder_clockwise() -> None:
    # Two players hold exactly one ace. The old code let the last seat iterated
    # win, which was arbitrary; the partner is now the first one to the left.
    result = detect_troel(hands(s1=[ACE_C, ACE_D, ACE_H], s3=[ACE_S], s2=[]))
    assert result is not None
    assert result.lead == Seat(1)
    assert result.partner == Seat(3)
    assert result.trump is Suit.SPADES


def test_four_aces_makes_hearts_trump_and_the_king_holder_the_partner() -> None:
    result = detect_troel(hands(s0=[ACE_C, ACE_D, ACE_H, ACE_S], s2=[KING_H]))
    assert result is not None
    assert result.lead == Seat(0)
    assert result.partner == Seat(2)
    assert result.trump is Suit.HEARTS


def test_four_aces_falls_back_to_the_queen_of_hearts() -> None:
    result = detect_troel(hands(s0=[ACE_C, ACE_D, ACE_H, ACE_S, KING_H], s3=[QUEEN_H]))
    assert result is not None
    assert result.partner == Seat(3)
    assert result.trump is Suit.HEARTS
