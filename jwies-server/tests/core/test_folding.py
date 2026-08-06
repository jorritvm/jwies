"""Giving up a lost round.

Once a contract can no longer be made, the declaring side may stop playing it
out. Giving up concedes every remaining trick to the defenders, so the round is
settled on the tricks the declaring side already has - the worst total still
reachable for them. That is what makes it theirs alone to offer: the defenders
cannot come out behind, so nobody asks them. With two declarers both partners
must agree, because conceding spends the partner's points too.

Whether it *costs* anything is a separate question, kept in
``payout_is_settled``. On the shipped scales the solo contracts (solo, solo
slim, misere, abondance) are fined a flat amount, so conceding changes nothing;
the duo contracts pay per missing trick, so every trick given up is real money
and the client warns before the player commits.
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
from jwies_core.scoring import RoundResult, payout_is_settled, score_round
from jwies_core.seats import Seat

TEMPLATES = Path(__file__).resolve().parents[3] / "config"


DUO_BIDS = (BidType.ASK, BidType.ALONE, BidType.JOIN)
# Abondance and solo need a trump chosen with the bid; these three do not, so a
# policy can pick them blind.
SOLO_BIDS = (BidType.MISERE, BidType.MISERE_OUVERTE, BidType.SOLO_SLIM)


def _choose_bid(options: tuple[Bid, ...], preference: tuple[BidType, ...] = DUO_BIDS) -> Bid:
    """Bid something rather than nothing.

    Taking ``options[0]`` would be simpler but it is always ``pass``, and four
    passes redeal - forever. The same policy as ``tests/e2e/conftest.py``.
    ``preference`` picks which family of contract the table steers towards,
    which is what decides whether folding can come up at all.
    """
    by_type = {option.type: option for option in options}
    for wanted in preference:
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
    ruleset: Ruleset,
    scale: ScoringScale,
    *,
    stop_early: bool = False,
    declarer_count: int | None = None,
) -> GameEngine:
    """An engine parked at the first moment folding is on offer.

    Everyone always plays their first legal option, so a game is a pure function
    of its seed - but whether *that* game produces a bust contract with tricks to
    spare is luck, so seeds are tried until one does. With ``stop_early`` the
    engine is handed back as soon as a contract exists instead, which is a
    position where folding must be refused.

    ``declarer_count`` narrows the search to a contract played by that many
    seats. It matters because a lone declarer conceding ends the round on the
    spot, while a pair needs both partners to agree. Two declarers are the rare
    case under this policy - the first bust troel turns up around seed 58 -
    which is why the search runs a good deal wider than it looks like it needs.
    """
    for seed in range(400):
        engine = GameEngine(ruleset, scale, rng=random.Random(seed))
        engine.start_round()
        # Bounded rather than `while True`: a policy that cannot reach a
        # contract would otherwise hang the whole suite, which it once did.
        for _ in range(300):
            if engine.phase is Phase.PLAYING or not _answer(engine):
                break
        if engine.phase is not Phase.PLAYING:
            continue
        contract = engine.round.contract
        if declarer_count is not None and (
            contract is None or len(contract.declarers) != declarer_count
        ):
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
    raw = yaml.safe_load((TEMPLATES / "scoring" / "kaartclubs.yaml").read_text(encoding="utf-8"))
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
    def test_a_bust_duo_contract_is_still_worth_playing(self) -> None:
        # The duo contracts are the ones charged per missing trick, so every
        # trick a bust declaring pair claws back is money and folding is refused.
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        alliance = contract(ContractKey.ALLIANCE, 8, declarers=(0, 2))
        assert not payout_is_settled(alliance, taken=2, remaining=4, scale=scale)

    def test_the_last_trick_settles_it(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        alliance = contract(ContractKey.ALLIANCE, 8, declarers=(0, 2))
        assert payout_is_settled(alliance, taken=2, remaining=0, scale=scale)

    def test_a_bust_solo_contract_settles_immediately(self) -> None:
        """The whole point of the flat penalties: nothing left to play for.

        Per docs/game/rules.md section 7.2 a failed solo slim costs a flat 20 a
        head however the rest of the tricks fall, so the table may stop at once.
        """
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        slim = contract(ContractKey.SOLO_SLIM, 13)
        assert payout_is_settled(slim, taken=2, remaining=6, scale=scale)

    def test_a_flat_penalty_settles_a_duo_contract_too(self, tmp_path: Path) -> None:
        """A table that wants to stop early on the duo contracts as well."""
        alliance = contract(ContractKey.ALLIANCE, 8, declarers=(0, 2))
        assert payout_is_settled(alliance, taken=2, remaining=4, scale=flat_scale(tmp_path))


def declarers_of(engine: GameEngine) -> tuple[Seat, ...]:
    contract = engine.round.contract
    assert contract is not None
    return tuple(Seat(seat) for seat in contract.declarers)


def defenders_of(engine: GameEngine) -> tuple[Seat, ...]:
    contract = engine.round.contract
    assert contract is not None
    return tuple(Seat(seat) for seat in contract.defenders)


class TestTheDeclaringSideGivingUp:
    """Driving a real engine to a conceded round.

    Giving up hands the defenders every trick that is left, so it is the
    declaring side's call alone and nobody else is asked. ``klassiek`` plus a
    flat penalty keeps these tests on a position where conceding is also free,
    so what they check is the mechanism rather than the arithmetic.
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
        engine = play_until_bust(klassiek, flat, stop_early=True)
        assert not engine.folding_is_offered()
        with pytest.raises(IllegalAction, match="niets op te geven"):
            engine.apply(declarers_of(engine)[0], Fold())

    def test_a_defender_may_not_give_up(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        """It is not their contract, and it would be their gift to refuse."""
        engine = play_until_bust(klassiek, flat)
        with pytest.raises(IllegalAction, match="enkel de spelende partij"):
            engine.apply(defenders_of(engine)[0], Fold())
        assert engine.round.folded == set()

    def test_a_lone_declarer_ends_it_on_his_own(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        """Nobody else's points are his to spend, so nobody else is asked."""
        engine = play_until_bust(klassiek, flat, declarer_count=1)
        events = engine.apply(declarers_of(engine)[0], Fold())
        assert any(isinstance(event, RoundScored) for event in events)

    def test_one_of_two_declarers_is_not_enough(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        """Conceding costs the partner points too, so he gets a say."""
        engine = play_until_bust(klassiek, flat, declarer_count=2)
        declarers = declarers_of(engine)
        events = engine.apply(declarers[0], Fold())
        assert [type(event) for event in events] == [FoldingChanged]
        assert engine.round.folded == {declarers[0]}
        assert not any(isinstance(event, RoundScored) for event in events)

    def test_a_repeated_vote_changes_nothing(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat, declarer_count=2)
        first = declarers_of(engine)[0]
        engine.apply(first, Fold())
        assert engine.apply(first, Fold()) == []

    def test_a_vote_can_be_withdrawn(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat, declarer_count=2)
        first = declarers_of(engine)[0]
        engine.apply(first, Fold())
        engine.apply(first, Fold(fold=False))
        assert engine.round.folded == set()

    def test_you_may_fold_out_of_turn(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        """Giving up is not a move, so nobody waits for the prompt."""
        engine = play_until_bust(klassiek, flat)
        on_turn = engine.pending()
        assert on_turn is not None
        off_turn = next(seat for seat in declarers_of(engine) if seat != on_turn.seat)
        engine.apply(off_turn, Fold())
        assert off_turn in engine.round.folded

    def test_the_whole_declaring_side_ends_the_round(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        engine = play_until_bust(klassiek, flat)
        before = engine.round.declarer_tricks

        events: list[object] = []
        for seat in declarers_of(engine):
            events = engine.apply(seat, Fold())

        scored = [event for event in events if isinstance(event, RoundScored)]
        assert len(scored) == 1
        assert scored[0].folded is True
        assert scored[0].made is False
        assert scored[0].tricks_made == before, "de resterende slagen zijn voor de tegenpartij"

    def test_conceding_is_settled_as_the_declaring_sides_worst_case(
        self, klassiek: Ruleset, flat: ScoringScale
    ) -> None:
        """ "Remaining tricks to the defenders", stated in points.

        The tricks themselves are not handed over - no cards changed hands, and
        the deck order for the next deal follows what was really won. What is
        conceded is the score: the round is settled on the tricks the declaring
        side has, which is the worst total still reachable for them.
        """
        engine = play_until_bust(klassiek, flat)
        contract = engine.round.contract
        assert contract is not None
        reachable = contract.reachable_tricks(
            engine.round.declarer_tricks, engine.tricks_remaining()
        )

        events: list[object] = []
        for seat in declarers_of(engine):
            events = engine.apply(seat, Fold())
        scored = next(event for event in events if isinstance(event, RoundScored))

        assert scored.tricks_made == min(reachable), "afgerekend op het slechtste bereikbare aantal"
        worst = min(
            score_round(RoundResult(contract, total, engine.round.multiplier), flat)[
                declarers_of(engine)[0]
            ]
            for total in reachable
        )
        assert scored.deltas[declarers_of(engine)[0]] == worst

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

        for seat in declarers_of(engine):
            engine.apply(seat, Fold())
        assert len(engine._deck) == 52
        assert len(set(engine._deck)) == 52

    def test_the_totals_still_sum_to_zero(self, klassiek: Ruleset, flat: ScoringScale) -> None:
        engine = play_until_bust(klassiek, flat)
        for seat in declarers_of(engine):
            engine.apply(seat, Fold())
        assert sum(engine.totals.values()) == Decimal(0)


class TestSayingSoWhenTheContractDies:
    """A dead contract is announced once, because a dead round it is not.

    Players reasonably assume there is nothing left to play for. On a duo
    contract there very much is - the penalty runs per missing trick - and
    nothing else in the game would tell them. The Dutch wording lives in the
    server's presenter and is checked there.
    """

    def test_it_is_announced_once_and_once_only(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        engine, _ = play_until_contract_dies(klassiek, scale)

        later = 0
        while engine.phase is Phase.PLAYING:
            later += sum(isinstance(e, ContractLost) for e in _answer_and_collect(engine))
        assert later == 0, "de aankondiging kwam meer dan een keer"

    def test_giving_up_is_offered_as_soon_as_the_contract_dies(self) -> None:
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        _, event = play_until_contract_dies(klassiek, scale)
        assert event.folding_offered is True

    def test_it_warns_that_a_duo_contract_still_pays_per_trick(self) -> None:
        """Giving up is allowed here, but it is not free - hence the warning."""
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        _, event = play_until_contract_dies(klassiek, scale)
        assert event.contract.spec.key in {ContractKey.ALLIANCE, ContractKey.ALONE}
        assert event.payout_settled is False

    def test_a_flat_penalty_costs_nothing_to_concede(self, tmp_path: Path) -> None:
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        _, event = play_until_contract_dies(klassiek, flat_scale(tmp_path))
        assert event.folding_offered is True
        assert event.payout_settled is True


class TestASoloContractCanBeGivenUpOnTheShippedScales:
    """The case that motivated the flat penalties, driven end to end.

    No hand-built scale here: plain ``kaartclubs.yaml``. The seed found lands on
    a solo slim that drops the very first trick - a flat 20 a head however the
    other twelve fall, so there is genuinely nothing left to play for and the
    offer arrives at once instead of at the last trick. This is the position the
    old scale handled worst: twelve pointless tricks, and a bill that grew with
    every one of them.
    """

    def _bust_solo(self) -> GameEngine:
        klassiek = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
        scale = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
        for seed in range(50):
            engine = GameEngine(klassiek, scale, rng=random.Random(seed))
            engine.start_round()
            for _ in range(400):
                prompt = engine.pending()
                if prompt is None:
                    break
                if prompt.kind is PromptKind.BID:
                    engine.apply(
                        prompt.seat,
                        PlaceBid(bid=_choose_bid(prompt.bid_options, SOLO_BIDS)),
                    )
                    continue
                if engine.folding_is_offered() and engine.tricks_remaining() > 1:
                    return engine
                _answer(engine)
        raise AssertionError("geen zaad gevonden met een gesneuveld solocontract")

    def test_the_offer_arrives_with_tricks_still_to_play(self) -> None:
        engine = self._bust_solo()
        assert engine.tricks_remaining() > 1
        assert engine.folding_is_offered()

    def test_the_table_can_actually_stop(self) -> None:
        engine = self._bust_solo()
        events: list[object] = []
        for seat in declarers_of(engine):
            events = engine.apply(seat, Fold())
        scored = [event for event in events if isinstance(event, RoundScored)]
        assert len(scored) == 1
        assert scored[0].folded is True
        assert sum(engine.totals.values()) == Decimal(0)

    def test_stopping_early_costs_exactly_the_same_as_playing_on(self) -> None:
        """The property that makes it safe, on the scale players actually use.

        ``_bust_solo`` is deterministic, so the two engines start from the
        same position and the only difference is what happens next.
        """
        stopped = self._bust_solo()
        for seat in declarers_of(stopped):
            stopped.apply(seat, Fold())

        played_out = self._bust_solo()
        while played_out.phase is Phase.PLAYING:
            _answer(played_out)

        assert stopped.totals == played_out.totals


def test_a_ruleset_can_forbid_folding(tmp_path: Path) -> None:
    source = (TEMPLATES / "ruleset" / "klassiek.yaml").read_text(encoding="utf-8")
    strict = tmp_path / "streng.yaml"
    strict.write_text(source + "\n  opgeven_toegelaten: false\n", encoding="utf-8")
    assert load_ruleset(strict).play.folding_allowed is False
    assert load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml").play.folding_allowed is True
