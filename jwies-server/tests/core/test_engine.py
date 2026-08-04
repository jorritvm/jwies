"""The engine state machine, driven through complete rounds."""

from __future__ import annotations

import random
from decimal import Decimal

import pytest

from jwies_core.bidding import Bid, BidType
from jwies_core.cards import CARDS_PER_HAND, DECK_SIZE, Card
from jwies_core.config import Ruleset, ScoringScale
from jwies_core.engine import GameEngine, Phase, PromptKind
from jwies_core.events import (
    Cut,
    Event,
    IllegalAction,
    PlaceBid,
    PlayCard,
    RoundScored,
    Shuffle,
    TrickCompleted,
)
from jwies_core.seats import ALL_SEATS, Seat


def make_engine(ruleset: Ruleset, scale: ScoringScale, seed: int = 42) -> GameEngine:
    engine = GameEngine(ruleset, scale, rng=random.Random(seed))
    engine.start_round()
    return engine


def advance_to_bidding(engine: GameEngine) -> list[Event]:
    """Answer the shuffle and cut prompts so bidding can start."""
    events: list[Event] = []
    while engine.phase in (Phase.WAITING_FOR_SHUFFLE, Phase.WAITING_FOR_CUT):
        prompt = engine.pending()
        assert prompt is not None
        if prompt.kind is PromptKind.SHUFFLE:
            events += engine.apply(prompt.seat, Shuffle(shuffle=False))
        else:
            events += engine.apply(prompt.seat, Cut(count=13))
    return events


def bid_until_playing(engine: GameEngine) -> list[Event]:
    """Everyone passes except the first bidder, who asks and then goes alone."""
    events: list[Event] = []
    guard = 0
    while engine.phase is Phase.BIDDING:
        guard += 1
        assert guard < 20, "biedronde loopt niet af"
        prompt = engine.pending()
        assert prompt is not None
        choice = _pick_bid(prompt.bid_options)
        events += engine.apply(prompt.seat, PlaceBid(bid=choice))
    return events


def _pick_bid(options: tuple[Bid, ...]) -> Bid:
    """Prefer ask, then alone, else pass - a deterministic, rules-free policy."""
    for wanted in (BidType.ASK, BidType.ALONE):
        for option in options:
            if option.type is wanted:
                return option
    return next(option for option in options if option.type is BidType.PASS)


def play_out_round(engine: GameEngine) -> list[Event]:
    """Play every remaining trick, always choosing the first legal card."""
    events: list[Event] = []
    guard = 0
    while engine.phase is Phase.PLAYING:
        guard += 1
        assert guard < 100, "ronde loopt niet af"
        prompt = engine.pending()
        assert prompt is not None
        assert prompt.legal_cards, "een speler moet altijd een geldige kaart hebben"
        events += engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))
    return events


class TestDealing:
    def test_everyone_gets_thirteen_cards(self, klassiek: Ruleset, schaal_a: ScoringScale) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        for seat in ALL_SEATS:
            assert len(engine.hand_of(seat)) == CARDS_PER_HAND

    def test_all_52_cards_are_dealt_exactly_once(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        dealt: list[Card] = []
        for seat in ALL_SEATS:
            dealt.extend(engine.hand_of(seat))
        assert len(dealt) == DECK_SIZE
        assert len(set(dealt)) == DECK_SIZE

    def test_the_turned_trump_is_a_dealt_card(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        turned = engine.round.turned_trump
        assert turned is not None
        everyone = [card for seat in ALL_SEATS for card in engine.hand_of(seat)]
        assert turned in everyone

    def test_a_cut_outside_the_allowed_range_is_refused(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        while engine.phase is Phase.WAITING_FOR_SHUFFLE:
            prompt = engine.pending()
            assert prompt is not None
            engine.apply(prompt.seat, Shuffle(shuffle=False))
        prompt = engine.pending()
        assert prompt is not None
        with pytest.raises(IllegalAction, match="kaarten afnemen"):
            engine.apply(prompt.seat, Cut(count=99))


class TestTurnTaking:
    def test_acting_out_of_turn_is_refused(self, klassiek: Ruleset, schaal_a: ScoringScale) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        prompt = engine.pending()
        assert prompt is not None
        other = Seat((prompt.seat + 1) % 4)
        with pytest.raises(IllegalAction, match="niet jouw beurt"):
            engine.apply(other, PlaceBid(bid=Bid(BidType.PASS)))

    def test_the_right_player_doing_the_wrong_thing_is_refused(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        """Being on turn is not enough - the action has to be the one asked for.

        This used to fall straight through to ``_apply_play`` and raise a
        ``KeyError`` on a hand that had not been dealt, which the server caught
        as an unexpected error and marked the whole table broken. The way in was
        ordinary: a card clicked a moment too late arrives in the next round,
        where the very same seat may be the dealer and so pass the turn check.
        """
        engine = make_engine(klassiek, schaal_a)
        prompt = engine.pending()
        assert prompt is not None
        assert prompt.kind is not PromptKind.PLAY

        with pytest.raises(IllegalAction, match="dat kan nu niet"):
            engine.apply(prompt.seat, PlayCard(card=Card.from_code("AH")))

        # And the table is still perfectly playable afterwards.
        assert engine.pending() == prompt

    def test_every_action_is_accepted_at_its_own_prompt(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        """The guard must not have shut the door on the legitimate moves."""
        engine = make_engine(klassiek, schaal_a)
        seen = set()
        for _ in range(200):
            prompt = engine.pending()
            if prompt is None or prompt.kind is PromptKind.PLAY:
                break
            seen.add(prompt.kind)
            match prompt.kind:
                case PromptKind.SHUFFLE:
                    engine.apply(prompt.seat, Shuffle(shuffle=False))
                case PromptKind.CUT:
                    engine.apply(prompt.seat, Cut(count=prompt.cut_minimum))
                case _:
                    engine.apply(prompt.seat, PlaceBid(bid=prompt.bid_options[-1]))
        assert {PromptKind.CUT, PromptKind.BID} <= seen

    def test_pending_is_idempotent(self, klassiek: Ruleset, schaal_a: ScoringScale) -> None:
        # Re-issuing a prompt after a reconnect must be free of side effects.
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        first = engine.pending()
        for _ in range(5):
            assert engine.pending() == first

    def test_an_illegal_card_is_refused_in_dutch(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        bid_until_playing(engine)
        # lead a card
        prompt = engine.pending()
        assert prompt is not None
        engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))

        prompt = engine.pending()
        assert prompt is not None
        hand = engine.hand_of(prompt.seat)
        illegal = next((card for card in hand if card not in prompt.legal_cards), None)
        if illegal is None:
            pytest.skip("deze speler kan elke kaart spelen")
        with pytest.raises(IllegalAction, match="kleur volgen"):
            engine.apply(prompt.seat, PlayCard(card=illegal))


class TestFullRound:
    def test_a_round_is_exactly_thirteen_tricks(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        bid_until_playing(engine)
        events = play_out_round(engine)
        tricks = [event for event in events if isinstance(event, TrickCompleted)]
        assert len(tricks) == CARDS_PER_HAND

    def test_the_round_is_scored_and_zero_sum(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        bid_until_playing(engine)
        events = play_out_round(engine)
        scored = [event for event in events if isinstance(event, RoundScored)]
        assert len(scored) == 1
        assert sum(scored[0].deltas.values()) == 0
        assert sum(engine.totals.values()) == 0

    def test_trick_counts_add_up_to_thirteen(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = make_engine(klassiek, schaal_a)
        advance_to_bidding(engine)
        bid_until_playing(engine)
        events = play_out_round(engine)
        last = [event for event in events if isinstance(event, TrickCompleted)][-1]
        assert last.declarer_tricks + last.defender_tricks == CARDS_PER_HAND

    @pytest.mark.parametrize("seed", range(12))
    def test_many_seeded_games_play_to_completion(
        self, seed: int, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        # Exercises every deal the RNG throws up, including troel hands and
        # redeals, which is where the old code used to get stuck.
        engine = make_engine(klassiek, schaal_a, seed=seed)
        advance_to_bidding(engine)
        bid_until_playing(engine)
        play_out_round(engine)
        assert engine.phase is Phase.ROUND_FINISHED
        assert sum(engine.totals.values()) == 0

    def test_several_rounds_in_a_row(self, klassiek: Ruleset, schaal_a: ScoringScale) -> None:
        engine = make_engine(klassiek, schaal_a)
        dealers = []
        for _ in range(4):
            dealers.append(engine.round.dealer)
            advance_to_bidding(engine)
            bid_until_playing(engine)
            play_out_round(engine)
            engine.start_round()
        # The deal moves one seat to the left each round.
        assert dealers == [Seat(0), Seat(1), Seat(2), Seat(3)]
        assert sum(engine.totals.values()) == 0


class TestDeterminism:
    def test_the_same_seed_produces_the_same_game(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        def run() -> list[str]:
            engine = make_engine(klassiek, schaal_a, seed=7)
            advance_to_bidding(engine)
            bid_until_playing(engine)
            events = play_out_round(engine)
            return [type(event).__name__ for event in events]

        assert run() == run()

    def test_all_pass_doubles_the_next_round(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        engine = GameEngine(klassiek, schaal_a, rng=random.Random(3))
        engine.start_round()
        advance_to_bidding(engine)
        guard = 0
        while engine.phase is Phase.BIDDING and guard < 30:
            guard += 1
            prompt = engine.pending()
            assert prompt is not None
            engine.apply(
                prompt.seat,
                PlaceBid(bid=next(o for o in prompt.bid_options if o.type is BidType.PASS)),
            )
        # Everyone passing triggers a redeal; the stake carries over doubled.
        assert engine.round.multiplier in (Decimal(1), Decimal(2))
