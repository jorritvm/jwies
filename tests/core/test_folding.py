"""Stopping a lost round early, by unanimous agreement.

The rule the table wants is "this round is decided, let's deal again". The rule
the engine can safely offer is narrower, and the difference matters: a contract
that has gone down is paid *per missing trick*, so a bust declarer is normally
still playing for real money with every trick he claws back. Stopping early
would hand that money to the defenders.

So folding is only offered when the payout is already fixed whatever happens -
then agreeing costs nobody anything. On the shipped scales that means the last
trick and little else; a table that wants to use this in earnest sets
``per_slag_tekort: 0`` on the contracts it cares about.
"""

from __future__ import annotations

import random
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from jwies_core.bidding import Bid, BidType
from jwies_core.config import Ruleset, ScoringScale, load_ruleset, load_scoring_scale
from jwies_core.contracts import CONTRACT_CATALOG, Contract, ContractKey
from jwies_core.engine import GameEngine, Phase, PromptKind
from jwies_core.events import (
    ContractLost,
    Cut,
    Fold,
    FoldingChanged,
    IllegalAction,
    PlaceBid,
    PlayCard,
    RoundScored,
    Shuffle,
)
from jwies_core.scoring import payout_is_settled
from jwies_core.seats import ALL_SEATS, Seat

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"


def _choose_bid(options: tuple[Bid, ...]) -> Bid:
    """Bid something rather than nothing.

    Taking ``options[0]`` would be simpler but it is always ``pass``, and four
    passes redeal - forever. The same policy as ``tests/e2e/conftest.py``.
    """
    by_type = {option.type: option for option in options}
    for wanted in (BidType.ASK, BidType.ALONE, BidType.JOIN):
        if wanted in by_type:
            return by_type[wanted]
    return by_type[BidType.PASS]


def _answer(engine: GameEngine) -> bool:
    """Take one deterministic step. False when the engine wants nothing."""
    prompt = engine.pending()
    if prompt is None:
        return False
    match prompt.kind:
        case PromptKind.SHUFFLE:
            engine.apply(prompt.seat, Shuffle(shuffle=False))
        case PromptKind.CUT:
            engine.apply(prompt.seat, Cut(count=prompt.cut_minimum))
        case PromptKind.BID:
            engine.apply(prompt.seat, PlaceBid(bid=_choose_bid(prompt.bid_options)))
        case PromptKind.PLAY:
            engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))
    return True


def play_until_bust(
    ruleset: Ruleset, scale: ScoringScale, *, stop_early: bool = False
) -> GameEngine:
    """An engine parked at the first moment folding is on offer.

    Everyone always plays their first legal option, so a game is a pure function
    of its seed - but whether *that* game produces a bust contract with tricks to
    spare is luck, so seeds are tried until one does. With ``stop_early`` the
    engine is handed back as soon as a contract exists instead, which is a
    position where folding must be refused.
    """
    for seed in range(50):
        engine = GameEngine(ruleset, scale, rng=random.Random(seed))
        engine.start_round()
        # Bounded rather than `while True`: a policy that cannot reach a
        # contract would otherwise hang the whole suite, which it once did.
        for _ in range(300):
            if engine.phase is Phase.PLAYING or not _answer(engine):
                break
        if engine.phase is not Phase.PLAYING:
            continue
        if stop_early:
            return engine
        while engine.phase is Phase.PLAYING:
            if engine.folding_is_offered() and engine.tricks_remaining() > 1:
                return engine
            if not _answer(engine):
                break
    raise AssertionError("geen zaad gevonden waarin een contract vroeg genoeg sneuvelt")


def flat_scale(tmp_path: Path) -> ScoringScale:
    """Schaal A with every per-missing-trick penalty set to zero.

    Built by rewriting the parsed YAML rather than the text: not every contract
    spells `per_overslag: 0`, so a string replace silently leaves some of them
    paying per trick - which is exactly the state in which folding is refused.
    """
    raw = yaml.safe_load((TEMPLATES / "scoring" / "schaal_a.yaml").read_text(encoding="utf-8"))
    for entry in raw["contracten"].values():
        entry["per_slag_tekort"] = 0
    path = tmp_path / "vlak.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return load_scoring_scale(path)


def _answer_and_collect(engine: GameEngine) -> list[object]:
    """One step, handing back the events it produced."""
    prompt = engine.pending()
    if prompt is None:
        return []
    match prompt.kind:
        case PromptKind.SHUFFLE:
            return engine.apply(prompt.seat, Shuffle(shuffle=False))
        case PromptKind.CUT:
            return engine.apply(prompt.seat, Cut(count=prompt.cut_minimum))
        case PromptKind.BID:
            return engine.apply(prompt.seat, PlaceBid(bid=_choose_bid(prompt.bid_options)))
        case _:
            return engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))


def play_until_contract_dies(
    ruleset: Ruleset, scale: ScoringScale
) -> tuple[GameEngine, ContractLost]:
    """Park an engine on the trick where the contract became unmakeable."""
    for seed in range(50):
        engine = GameEngine(ruleset, scale, rng=random.Random(seed))
        engine.start_round()
        for _ in range(400):
            events = _answer_and_collect(engine)
            if not events and engine.pending() is None:
                break
            lost = next((e for e in events if isinstance(e, ContractLost)), None)
            if lost is not None:
                return engine, lost
            if engine.phase is not Phase.PLAYING and engine.round.contract is None:
                continue
        # This seed's contract was made; try the next.
    raise AssertionError("geen zaad gevonden waarin een contract sneuvelt")


def contract(key: ContractKey, required: int, declarers: tuple[int, ...] = (0,)) -> Contract:
    spec = CONTRACT_CATALOG[key]
    return Contract(
        spec=spec,
        declarers=declarers,
        defenders=tuple(seat for seat in range(4) if seat not in declarers),
        trump=None,
        tricks_required=required,
        leader=declarers[0],
    )


class TestWhenAContractIsBeyondSaving:
    """``can_still_be_made`` searches the reachable totals, so one rule covers
    both an ``at_least`` contract running out of tricks and an ``exactly`` one
    overshooting."""

    def test_an_alliance_dies_when_the_tricks_run_out(self) -> None:
        alliance = contract(ContractKey.ALLIANCE, 8, declarers=(0, 2))
        assert alliance.can_still_be_made(taken=5, remaining=3)
        assert not alliance.can_still_be_made(taken=5, remaining=2)

    def test_a_solo_slim_dies_on_the_first_trick_it_drops(self) -> None:
        slim = contract(ContractKey.SOLO_SLIM, 13)
        assert slim.can_still_be_made(taken=4, remaining=9)
        assert not slim.can_still_be_made(taken=4, remaining=8)

    def test_a_misere_dies_the_moment_its_declarer_wins_a_trick(self) -> None:
        # The other direction entirely: here taking tricks is what kills it.
        misere = contract(ContractKey.MISERE, 0)
        assert misere.can_still_be_made(taken=0, remaining=6)
        assert not misere.can_still_be_made(taken=1, remaining=6)


class TestWhenTheMoneyIsAlreadyFixed:
    def test_a_bust_contract_is_normally_still_worth_playing(self) -> None:
        # This is the finding that shaped the whole feature: every trick a bust
        # declarer takes back is money, so folding would not be free.
        scale = load_scoring_scale(TEMPLATES / "scoring" / "schaal_a.yaml")
        slim = contract(ContractKey.SOLO_SLIM, 13)
        assert not payout_is_settled(slim, taken=2, remaining=6, scale=scale)

    def test_the_last_trick_settles_it(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "schaal_a.yaml")
        slim = contract(ContractKey.SOLO_SLIM, 13)
        assert payout_is_settled(slim, taken=2, remaining=0, scale=scale)

    def test_a_flat_penalty_settles_it_immediately(self, tmp_path: Path) -> None:
        """The configuration this feature is actually for."""
        slim = contract(ContractKey.SOLO_SLIM, 13)
        assert payout_is_settled(slim, taken=2, remaining=6, scale=flat_scale(tmp_path))


class TestTheTableAgreeing:
    """Driving a real engine to a folded round.

    ``klassiek`` plus a flat penalty, because that is the only configuration in
    which the offer appears early enough to be worth testing.
    """

    @pytest.fixture
    def flat(self, tmp_path: Path) -> ScoringScale:
        return flat_scale(tmp_path)

    @pytest.fixture
    def klassiek(self) -> Ruleset:
        return load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")

    def test_folding_is_not_offered_while_the_contract_lives(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        engine = play_until_bust(klassiek, flat_scale, stop_early=True)
        assert not engine.folding_is_offered()
        with pytest.raises(IllegalAction, match="niets op te geven"):
            engine.apply(Seat(0), Fold())

    def test_one_vote_is_not_enough(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        assert engine.folding_is_offered()
        events = engine.apply(Seat(0), Fold())
        assert [type(event) for event in events] == [FoldingChanged]
        assert engine.round.folded == {Seat(0)}
        assert not any(isinstance(event, RoundScored) for event in events)

    def test_a_repeated_vote_changes_nothing(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        engine.apply(Seat(0), Fold())
        assert engine.apply(Seat(0), Fold()) == []

    def test_a_vote_can_be_withdrawn(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        engine.apply(Seat(0), Fold())
        engine.apply(Seat(0), Fold(fold=False))
        assert engine.round.folded == set()

    def test_you_may_fold_out_of_turn(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        """The table is deciding together, so nobody waits for the prompt."""
        engine = play_until_bust(klassiek, flat)
        on_turn = engine.pending()
        assert on_turn is not None
        off_turn = next(seat for seat in ALL_SEATS if seat != on_turn.seat)
        engine.apply(off_turn, Fold())
        assert off_turn in engine.round.folded

    def test_all_four_ends_the_round(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        before = engine.round.declarer_tricks

        events: list[object] = []
        for seat in ALL_SEATS:
            events = engine.apply(seat, Fold())

        scored = [event for event in events if isinstance(event, RoundScored)]
        assert len(scored) == 1
        assert scored[0].folded is True
        assert scored[0].made is False
        assert scored[0].tricks_made == before, "de stand bevriest zoals ze was"

    def test_the_deck_survives_a_fold_mid_trick(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        """The engine asserts on 52 unique cards, so this would blow up loudly.

        A fold can land with cards already on the table for the current trick;
        they belong to nobody and are scooped up with the hands.
        """
        engine = play_until_bust(klassiek, flat)
        prompt = engine.pending()
        assert prompt is not None
        engine.apply(prompt.seat, PlayCard(card=prompt.legal_cards[0]))
        assert engine.round.trick, "er ligt nu een onvolledige slag"

        for seat in ALL_SEATS:
            engine.apply(seat, Fold())
        assert len(engine._deck) == 52
        assert len(set(engine._deck)) == 52

    def test_the_totals_still_sum_to_zero(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        for seat in ALL_SEATS:
            engine.apply(seat, Fold())
        assert sum(engine.totals.values()) == Decimal(0)


class TestSayingSoWhenTheContractDies:
    """A dead contract is announced once, because a dead round it is not.

    Players reasonably assume there is nothing left to play for. With the
    shipped scales there very much is - the penalty runs per missing trick - and
    nothing else in the game would tell them. The Dutch wording lives in the
    server's presenter and is checked there.
    """

    def test_it_is_announced_once_and_once_only(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "schaal_a.yaml")
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        engine, _ = play_until_contract_dies(klassiek, scale)

        later = 0
        while engine.phase is Phase.PLAYING:
            later += sum(isinstance(e, ContractLost) for e in _answer_and_collect(engine))
        assert later == 0, "de aankondiging kwam meer dan een keer"

    def test_it_knows_the_table_must_play_on(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "schaal_a.yaml")
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        _, event = play_until_contract_dies(klassiek, scale)
        assert event.folding_offered is False

    def test_it_knows_when_the_table_may_stop(self, tmp_path: Path) -> None:
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        _, event = play_until_contract_dies(klassiek, flat_scale(tmp_path))
        assert event.folding_offered is True


def test_a_ruleset_can_forbid_folding(tmp_path: Path) -> None:
    source = (TEMPLATES / "ruleset" / "klassiek.yaml").read_text(encoding="utf-8")
    strict = tmp_path / "streng.yaml"
    strict.write_text(source + "\n  opgeven_toegelaten: false\n", encoding="utf-8")
    assert load_ruleset(strict).play.folding_allowed is False
    assert load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml").play.folding_allowed is True
