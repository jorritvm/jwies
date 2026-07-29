"""Every contract type resolves correctly, and redeals happen when they should.

The generic full-round test only reaches 'alone' and 'troel', so each remaining
contract is driven here with a scripted bidding round.
"""

from __future__ import annotations

import random

import pytest
from jwies_core.bidding import Bid, BidType
from jwies_core.cards import Suit
from jwies_core.config import Ruleset, ScoringScale
from jwies_core.contracts import ContractKey
from jwies_core.engine import GameEngine, Phase, PromptKind
from jwies_core.events import (
    ContractEstablished,
    Cut,
    Event,
    PlaceBid,
    PlayCard,
    RedealRequired,
    Shuffle,
    TrickCompleted,
)
from jwies_core.seats import ALL_SEATS


def start(ruleset: Ruleset, scale: ScoringScale, seed: int) -> GameEngine:
    engine = GameEngine(ruleset, scale, rng=random.Random(seed))
    engine.start_round()
    while engine.phase in (Phase.WAITING_FOR_SHUFFLE, Phase.WAITING_FOR_CUT):
        prompt = engine.pending()
        assert prompt is not None
        if prompt.kind is PromptKind.SHUFFLE:
            engine.apply(prompt.seat, Shuffle(shuffle=False))
        else:
            engine.apply(prompt.seat, Cut(count=13))
    return engine


def seed_without_troel(ruleset: Ruleset, scale: ScoringScale) -> int:
    """A seed whose deal contains no forced troel, so bidding is free."""
    for seed in range(500):
        engine = start(ruleset, scale, seed)
        if engine.round.troel is None:
            return seed
    raise AssertionError("geen enkele deal zonder troel gevonden")


def bid_script(engine: GameEngine, script: list[Bid]) -> list[Event]:
    """Feed bids in turn order; anyone not scripted passes."""
    events: list[Event] = []
    index = 0
    guard = 0
    while engine.phase is Phase.BIDDING:
        guard += 1
        assert guard < 20
        prompt = engine.pending()
        assert prompt is not None
        if index < len(script):
            wanted = script[index]
            index += 1
        else:
            wanted = Bid(BidType.PASS)
        option = next(
            (
                candidate
                for candidate in prompt.bid_options
                if candidate.type is wanted.type and candidate.tricks == wanted.tricks
            ),
            None,
        )
        if option is None:
            option = next(o for o in prompt.bid_options if o.type is BidType.PASS)
        else:
            option = Bid(option.type, option.tricks, wanted.suit or option.suit)
        events += engine.apply(prompt.seat, PlaceBid(bid=option))
    return events


def established(events: list[Event]) -> ContractEstablished | None:
    found = [event for event in events if isinstance(event, ContractEstablished)]
    return found[0] if found else None


class TestContractResolution:
    def test_ask_and_join_forms_an_alliance_of_two(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.ASK), Bid(BidType.JOIN)])
        contract = established(events)
        assert contract is not None
        assert contract.contract.key is ContractKey.ALLIANCE
        assert len(contract.contract.declarers) == 2
        assert len(contract.contract.defenders) == 2
        assert contract.contract.tricks_required == 8
        # An alliance plays in the turned trump.
        assert contract.trump is engine.round.turned_trump.suit  # type: ignore[union-attr]

    def test_abondance_uses_the_bidders_chosen_trump(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.ABONDANCE, tricks=10, suit=Suit.SPADES)])
        contract = established(events)
        assert contract is not None
        assert contract.contract.key is ContractKey.ABONDANCE_10
        assert contract.trump is Suit.SPADES
        assert contract.contract.tricks_required == 10
        assert len(contract.contract.declarers) == 1

    def test_misere_plays_without_trump(self, klassiek: Ruleset, schaal_a: ScoringScale) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.MISERE)])
        contract = established(events)
        assert contract is not None
        assert contract.contract.key is ContractKey.MISERE
        assert contract.trump is None
        assert contract.contract.tricks_required == 0

    def test_solo_slim_plays_in_the_turned_trump(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.SOLO_SLIM)])
        contract = established(events)
        assert contract is not None
        assert contract.contract.key is ContractKey.SOLO_SLIM
        assert contract.trump is engine.round.turned_trump.suit  # type: ignore[union-attr]
        assert contract.contract.tricks_required == 13

    def test_declarer_leads_when_the_ruleset_says_so(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.MISERE)])
        contract = established(events)
        assert contract is not None
        assert klassiek.lead.misere is True
        assert contract.contract.leader == contract.contract.declarers[0]

    def test_alliance_leader_is_left_of_the_dealer(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        events = bid_script(engine, [Bid(BidType.ASK), Bid(BidType.JOIN)])
        contract = established(events)
        assert contract is not None
        assert contract.contract.leader == (engine.round.dealer + 1) % 4


class TestRedeal:
    def test_everyone_passing_triggers_a_redeal_with_the_same_dealer(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        dealer_before = engine.round.dealer
        events = bid_script(engine, [])  # everyone passes
        redeals = [event for event in events if isinstance(event, RedealRequired)]
        assert len(redeals) == 1
        assert redeals[0].reason == "all_passed"
        assert engine.round.dealer == dealer_before

    def test_a_withdrawn_ask_moves_the_deal_on(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        dealer_before = engine.round.dealer
        # seat asks, three pass, then the asker passes after all
        events = bid_script(
            engine,
            [
                Bid(BidType.ASK),
                Bid(BidType.PASS),
                Bid(BidType.PASS),
                Bid(BidType.PASS),
                Bid(BidType.PASS),
            ],
        )
        redeals = [event for event in events if isinstance(event, RedealRequired)]
        assert len(redeals) == 1
        assert redeals[0].reason == "ask_declined"
        assert engine.round.dealer == (dealer_before + 1) % 4

    def test_the_game_continues_normally_after_a_redeal(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        seed = seed_without_troel(klassiek, schaal_a)
        engine = start(klassiek, schaal_a, seed)
        bid_script(engine, [])
        # A fresh hand was dealt and we are ready to bid again.
        assert engine.phase in (
            Phase.WAITING_FOR_SHUFFLE,
            Phase.WAITING_FOR_CUT,
            Phase.BIDDING,
            Phase.PLAYING,
        )
        for seat in ALL_SEATS:
            assert len(engine.hand_of(seat)) in (0, 13)


class TestTroelInPlay:
    def test_a_troel_round_plays_to_completion(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        troel_seed = next(
            seed for seed in range(200) if start(klassiek, schaal_a, seed).round.troel is not None
        )
        engine = start(klassiek, schaal_a, troel_seed)
        assert engine.round.troel is not None
        events = bid_script(engine, [])
        contract = established(events)
        assert contract is not None
        assert contract.contract.key is ContractKey.TROEL
        assert len(contract.contract.declarers) == 2
        # The partner (fourth ace) opens, per klassiek.yaml.
        assert contract.contract.leader == contract.contract.declarers[1]

        played: list[Event] = []
        guard = 0
        while engine.phase is Phase.PLAYING:
            guard += 1
            assert guard < 100
            prompt = engine.pending()
            assert prompt is not None
            played += engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))
        assert len([e for e in played if isinstance(e, TrickCompleted)]) == 13

    def test_troel_eight_forces_the_highest_trump_on_the_first_card(
        self, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        assert klassiek.bidding.troel_tricks == 8
        assert klassiek.play.troel_must_lead_highest_trump is True
        troel_seed = next(
            seed for seed in range(200) if start(klassiek, schaal_a, seed).round.troel is not None
        )
        engine = start(klassiek, schaal_a, troel_seed)
        bid_script(engine, [])
        prompt = engine.pending()
        assert prompt is not None
        leader_hand = engine.hand_of(prompt.seat)
        trumps = [card for card in leader_hand if card.suit is engine.round.trump]
        if trumps:
            assert len(prompt.legal_cards) == 1
            assert prompt.legal_cards[0] == max(trumps, key=lambda c: c.rank)
        else:
            pytest.skip("de uitkomende speler heeft geen troef")
