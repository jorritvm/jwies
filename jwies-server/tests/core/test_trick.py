"""Trick rules: legal moves and trick winner."""

from __future__ import annotations

from jwies_core.cards import Card, Rank, Suit
from jwies_core.seats import Seat
from jwies_core.trick import PlayedCard, legal_moves, trick_winner


def played(seat: int, rank: Rank, suit: Suit) -> PlayedCard:
    return PlayedCard(seat=Seat(seat), card=Card(rank, suit))


class TestTrickWinner:
    def test_highest_of_the_led_suit_wins_without_trump(self) -> None:
        trick = [
            played(0, Rank.FIVE, Suit.HEARTS),
            played(1, Rank.KING, Suit.HEARTS),
            played(2, Rank.TWO, Suit.HEARTS),
            played(3, Rank.NINE, Suit.HEARTS),
        ]
        assert trick_winner(trick, trump=None) == Seat(1)

    def test_trump_beats_the_led_suit(self) -> None:
        trick = [
            played(0, Rank.ACE, Suit.HEARTS),
            played(1, Rank.TWO, Suit.SPADES),
            played(2, Rank.KING, Suit.HEARTS),
            played(3, Rank.THREE, Suit.HEARTS),
        ]
        assert trick_winner(trick, trump=Suit.SPADES) == Seat(1)

    def test_highest_trump_wins_when_several_are_played(self) -> None:
        trick = [
            played(0, Rank.ACE, Suit.HEARTS),
            played(1, Rank.TWO, Suit.SPADES),
            played(2, Rank.TEN, Suit.SPADES),
            played(3, Rank.THREE, Suit.SPADES),
        ]
        assert trick_winner(trick, trump=Suit.SPADES) == Seat(2)

    def test_a_discard_never_wins(self) -> None:
        trick = [
            played(0, Rank.TWO, Suit.HEARTS),
            played(1, Rank.ACE, Suit.CLUBS),
            played(2, Rank.ACE, Suit.DIAMONDS),
            played(3, Rank.THREE, Suit.HEARTS),
        ]
        assert trick_winner(trick, trump=Suit.SPADES) == Seat(3)


class TestLegalMoves:
    def test_leader_may_play_anything(self) -> None:
        hand = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.TWO, Suit.CLUBS)]
        assert legal_moves(hand, [], trump=Suit.SPADES) == hand

    def test_must_follow_suit_when_able(self) -> None:
        hand = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
        ]
        trick = [played(0, Rank.FIVE, Suit.HEARTS)]
        assert legal_moves(hand, trick, trump=Suit.SPADES) == [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.KING, Suit.HEARTS),
        ]

    def test_may_play_anything_when_unable_to_follow(self) -> None:
        hand = [Card(Rank.TWO, Suit.CLUBS), Card(Rank.ACE, Suit.SPADES)]
        trick = [played(0, Rank.FIVE, Suit.HEARTS)]
        assert legal_moves(hand, trick, trump=Suit.SPADES) == hand

    def test_troel_eight_forces_the_highest_trump_on_the_opening_lead(self) -> None:
        hand = [
            Card(Rank.TWO, Suit.CLUBS),
            Card(Rank.KING, Suit.HEARTS),
            Card(Rank.ACE, Suit.HEARTS),
        ]
        assert legal_moves(hand, [], trump=Suit.HEARTS, must_lead_highest_trump=True) == [
            Card(Rank.ACE, Suit.HEARTS)
        ]

    def test_troel_eight_obligation_lapses_without_any_trump(self) -> None:
        # The old code fell back to "your highest card overall" here, which is
        # not a rule anyone plays. Holding no trump simply frees the choice.
        hand = [Card(Rank.TWO, Suit.CLUBS), Card(Rank.ACE, Suit.SPADES)]
        assert legal_moves(hand, [], trump=Suit.HEARTS, must_lead_highest_trump=True) == hand

    def test_follow_suit_still_applies_under_the_troel_rule(self) -> None:
        hand = [Card(Rank.TWO, Suit.CLUBS), Card(Rank.ACE, Suit.HEARTS)]
        trick = [played(0, Rank.FIVE, Suit.CLUBS)]
        assert legal_moves(hand, trick, trump=Suit.HEARTS, must_lead_highest_trump=True) == [
            Card(Rank.TWO, Suit.CLUBS)
        ]
