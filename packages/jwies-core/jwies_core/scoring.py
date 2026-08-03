"""Point counting.

The old code had ``# todo: implement`` where this belongs, and the ``[points]``
settings in controller.ini were written by the settings dialog and read by
nothing. This module makes them real.

Points are zero-sum: what the winners receive, the losers pay. Every result of
``score_round`` sums to exactly zero, which is asserted as a property test.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from jwies_core.config.scoring_scale import ScoringScale, SoloPayment
from jwies_core.contracts import Contract
from jwies_core.seats import Seat

__all__ = ["RoundResult", "payout_is_settled", "score_round"]


@dataclass(frozen=True, slots=True)
class RoundResult:
    """Everything needed to settle one round."""

    contract: Contract
    tricks_made: int  # tricks taken by the declaring side
    multiplier: Decimal = Decimal(1)  # "iedereen paste vorige ronde"

    @property
    def made(self) -> bool:
        return self.contract.is_made(self.tricks_made)


def _contract_value(result: RoundResult, scale: ScoringScale) -> Decimal:
    """The value of the contract from the declaring side's point of view.

    Positive when the contract was made, negative when it went down.
    """
    score = scale.score_for(result.contract.spec.scoring_key)
    required = result.contract.tricks_required

    if result.made:
        if result.tricks_made == 13 and score.all_thirteen is not None:
            return score.all_thirteen
        overtricks = max(0, result.tricks_made - required)
        return score.base + score.per_overtrick * overtricks

    # Down. A misere is beaten by any trick at all, so "tricks short" is
    # measured as how far the wrong way the result went.
    if result.contract.spec.comparison == "exactly" and result.tricks_made > required:
        short = result.tricks_made - required
    else:
        short = max(1, required - result.tricks_made)

    value = score.base + score.undertrick_value * short
    if scale.losing_is_double:
        value *= 2
    return -value


def payout_is_settled(
    contract: Contract,
    taken: int,
    remaining: int,
    scale: ScoringScale,
    multiplier: Decimal = Decimal(1),
) -> bool:
    """Whether the money is already fixed, however the remaining tricks fall.

    This is what makes folding safe to offer: if every reachable outcome pays
    exactly the same, nobody can be worse off for agreeing to stop, so consent
    costs nothing.

    Be warned that it is rarely true. A contract that has gone down is paid per
    missing trick, and ``per_slag_tekort`` defaults to the full ``basis`` - so on
    all three shipped scales a bust declarer is still playing for real money
    with every trick he claws back. It settles only where a scale sets
    ``per_slag_tekort: 0``, or on the last trick.
    """
    values = {
        _contract_value(RoundResult(contract, total, multiplier), scale)
        for total in contract.reachable_tricks(taken, remaining)
    }
    return len(values) == 1


def score_round(result: RoundResult, scale: ScoringScale) -> dict[Seat, Decimal]:
    """Point deltas for all four seats. Always sums to zero."""
    value = _contract_value(result, scale) * result.multiplier

    declarers = [Seat(seat) for seat in result.contract.declarers]
    defenders = [Seat(seat) for seat in result.contract.defenders]

    if len(declarers) == 2:
        # Two against two: each loser pays one winner, so the amount each
        # player gains or loses is simply the contract value.
        per_defender = value
    elif scale.solo_payment is SoloPayment.PER_OPPONENT:
        # Schaal A: every opponent pays the full amount.
        per_defender = value
    else:
        # Schaal B: the tabulated value is the total, split over the opponents.
        per_defender = value / len(defenders)

    total_from_defenders = per_defender * len(defenders)
    per_declarer = total_from_defenders / len(declarers)

    deltas: dict[Seat, Decimal] = {}
    for seat in defenders:
        deltas[seat] = -per_defender
    for seat in declarers:
        deltas[seat] = per_declarer
    return deltas
