"""Card model: code round-trips, SVG ids, sorting."""

from __future__ import annotations

import random

import pytest

from jwies_core.cards import (
    DECK_SIZE,
    Card,
    Rank,
    Suit,
    full_deck,
    highest_of_suit,
    shuffled_deck,
    sort_for_hand,
)


def test_full_deck_has_52_unique_cards() -> None:
    deck = full_deck()
    assert len(deck) == DECK_SIZE
    assert len(set(deck)) == DECK_SIZE


@pytest.mark.parametrize("card", full_deck())
def test_code_round_trips_for_every_card(card: Card) -> None:
    assert Card.from_code(card.code) == card


def test_codes_match_the_legacy_pydealer_abbreviations() -> None:
    # These are the exact strings the old wire protocol used; the new JSON
    # protocol keeps them, so a mismatch here would break card rendering.
    assert Card(Rank.ACE, Suit.HEARTS).code == "AH"
    assert Card(Rank.TEN, Suit.SPADES).code == "10S"
    assert Card(Rank.QUEEN, Suit.DIAMONDS).code == "QD"
    assert Card(Rank.TWO, Suit.CLUBS).code == "2C"
    assert Card(Rank.KING, Suit.CLUBS).code == "KC"


def test_svg_element_ids_match_the_svg_cards_sheet() -> None:
    # svg-cards.svg names the ace "1" and uses singular suit names.
    assert Card(Rank.ACE, Suit.HEARTS).svg_element_id == "1_heart"
    assert Card(Rank.KING, Suit.SPADES).svg_element_id == "king_spade"
    assert Card(Rank.TEN, Suit.CLUBS).svg_element_id == "10_club"
    assert Card(Rank.JACK, Suit.DIAMONDS).svg_element_id == "jack_diamond"


@pytest.mark.parametrize("bad", ["", "H", "1H", "AX", "11S", "ah"])
def test_from_code_rejects_malformed_input(bad: str) -> None:
    with pytest.raises(ValueError):
        Card.from_code(bad)


def test_rank_ordering_is_trick_taking_order() -> None:
    assert Rank.TWO < Rank.TEN < Rank.JACK < Rank.QUEEN < Rank.KING < Rank.ACE


def test_sort_for_hand_groups_by_suit_then_rank() -> None:
    hand = [
        Card(Rank.ACE, Suit.HEARTS),
        Card(Rank.TWO, Suit.CLUBS),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.THREE, Suit.CLUBS),
    ]
    assert sort_for_hand(hand) == [
        Card(Rank.TWO, Suit.CLUBS),
        Card(Rank.THREE, Suit.CLUBS),
        Card(Rank.FIVE, Suit.SPADES),
        Card(Rank.KING, Suit.HEARTS),
        Card(Rank.ACE, Suit.HEARTS),
    ]


def test_shuffled_deck_is_reproducible_for_a_given_seed() -> None:
    assert shuffled_deck(random.Random(42)) == shuffled_deck(random.Random(42))
    assert shuffled_deck(random.Random(42)) != shuffled_deck(random.Random(43))


def test_highest_of_suit_returns_none_when_suit_is_absent() -> None:
    hand = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.HEARTS)]
    assert highest_of_suit(hand, Suit.HEARTS) == Card(Rank.ACE, Suit.HEARTS)
    # The old implementation returned the globally highest card here.
    assert highest_of_suit(hand, Suit.SPADES) is None
