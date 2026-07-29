"""The bidding ladder."""

from __future__ import annotations

from jwies_core.bidding import Bid, BidEntry, BidLadder, BidType
from jwies_core.cards import Suit
from jwies_core.config import Ruleset
from jwies_core.seats import Seat


def types(options: list[Bid]) -> set[BidType]:
    return {option.type for option in options}


def test_opening_bidder_may_ask_or_bid_anything(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    options = ladder.options_after([], Seat(0))
    assert BidType.PASS in types(options)
    assert BidType.ASK in types(options)
    assert BidType.SOLO_SLIM in types(options)
    # You cannot join before anyone has asked.
    assert BidType.JOIN not in types(options)


def test_join_is_offered_only_after_an_ask(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [BidEntry(seat=Seat(0), bid=Bid(BidType.ASK))]
    assert BidType.JOIN in types(ladder.options_after(entries, Seat(1)))
    # ...and never to the asker himself
    assert BidType.JOIN not in types(ladder.options_after(entries, Seat(0)))


def test_only_one_player_can_join(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [
        BidEntry(seat=Seat(0), bid=Bid(BidType.ASK)),
        BidEntry(seat=Seat(1), bid=Bid(BidType.JOIN)),
    ]
    assert BidType.JOIN not in types(ladder.options_after(entries, Seat(2)))


def test_a_higher_bid_removes_everything_below_it(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [BidEntry(seat=Seat(0), bid=Bid(BidType.ABONDANCE, tricks=10))]
    options = types(ladder.options_after(entries, Seat(1)))
    assert BidType.ASK not in options
    assert BidType.MISERE not in options  # ranks below abondance 10
    assert BidType.SOLO in options
    assert BidType.MISERE_OUVERTE in options


def test_abondance_levels_are_ordered(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [BidEntry(seat=Seat(0), bid=Bid(BidType.ABONDANCE, tricks=10))]
    tricks = {
        option.tricks
        for option in ladder.options_after(entries, Seat(1))
        if option.type is BidType.ABONDANCE
    }
    assert tricks == {11, 12}


def test_solo_slim_is_the_top_of_the_ladder(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [BidEntry(seat=Seat(0), bid=Bid(BidType.SOLO_SLIM))]
    assert types(ladder.options_after(entries, Seat(1))) == {BidType.PASS}


def test_asker_gets_a_final_say_after_three_passes(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [
        BidEntry(seat=Seat(0), bid=Bid(BidType.ASK)),
        BidEntry(seat=Seat(1), bid=Bid(BidType.PASS)),
        BidEntry(seat=Seat(2), bid=Bid(BidType.PASS)),
        BidEntry(seat=Seat(3), bid=Bid(BidType.PASS)),
    ]
    assert ladder.is_final_say(entries)
    options = ladder.options_after(entries, Seat(0))
    assert BidType.ALONE in types(options)
    assert BidType.ASK not in types(options)
    assert BidType.PASS in types(options)


def test_alone_carries_the_rulesets_trick_target(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [
        BidEntry(seat=Seat(0), bid=Bid(BidType.ASK)),
        *[BidEntry(seat=Seat(n), bid=Bid(BidType.PASS)) for n in (1, 2, 3)],
    ]
    alone = next(
        option for option in ladder.options_after(entries, Seat(0)) if option.type is BidType.ALONE
    )
    assert alone.tricks == klassiek.bidding.alone_tricks == 5


def test_troel_above_all_leaves_only_the_allowed_overbids(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    entries = [
        BidEntry(seat=Seat(0), bid=Bid(BidType.TROEL, suit=Suit.HEARTS), forced=True),
        BidEntry(seat=Seat(2), bid=Bid(BidType.TROEL, suit=Suit.HEARTS), forced=True),
    ]
    options = types(ladder.options_after(entries, Seat(1)))
    # klassiek.yaml lets only solo slim beat a troel
    assert options == {BidType.PASS, BidType.SOLO_SLIM}


def test_chosen_trump_contracts_require_a_suit(klassiek: Ruleset) -> None:
    ladder = BidLadder(klassiek)
    assert ladder.needs_suit(Bid(BidType.ABONDANCE, tricks=10)) is True
    assert ladder.needs_suit(Bid(BidType.SOLO)) is True
    # solo slim plays in the turned trump, so the bidder does not pick one
    assert ladder.needs_suit(Bid(BidType.SOLO_SLIM)) is False
    assert ladder.needs_suit(Bid(BidType.MISERE)) is False
    assert ladder.needs_suit(Bid(BidType.PASS)) is False
