"""Point counting against the two published scales.

The expected values come straight from docs/game_rules.md sections 7.2 and 7.3.
This is the part the old codebase never implemented at all.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from jwies_core.config import ScoringScale
from jwies_core.contracts import CONTRACT_CATALOG, Contract, ContractKey
from jwies_core.scoring import RoundResult, score_round
from jwies_core.seats import Seat


def contract(key: ContractKey, *, tricks_required: int | None = None) -> Contract:
    spec = CONTRACT_CATALOG[key]
    declarers = tuple(range(spec.declarer_count))
    defenders = tuple(seat for seat in range(4) if seat not in declarers)
    return Contract(
        spec=spec,
        declarers=declarers,
        defenders=defenders,
        trump=None,
        tricks_required=tricks_required or spec.tricks_required,
        leader=0,
    )


def deltas(
    key: ContractKey, tricks: int, scale: ScoringScale, *, required: int | None = None
) -> dict[Seat, Decimal]:
    return score_round(
        RoundResult(contract=contract(key, tricks_required=required), tricks_made=tricks),
        scale,
    )


class TestSchaalA:
    """Kleine schaal: every opponent pays the full amount."""

    def test_alliance_made_exactly(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.ALLIANCE, 8, schaal_a)
        assert result[Seat(0)] == 2
        assert result[Seat(1)] == 2
        assert result[Seat(2)] == -2
        assert result[Seat(3)] == -2

    def test_alliance_with_overtricks(self, schaal_a: ScoringScale) -> None:
        # 2 base + 1 per overtrick, two tricks over.
        result = deltas(ContractKey.ALLIANCE, 10, schaal_a)
        assert result[Seat(0)] == 4

    def test_alliance_all_thirteen_uses_the_fixed_value(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.ALLIANCE, 13, schaal_a)
        assert result[Seat(0)] == 14

    def test_alliance_two_tricks_short(self, schaal_a: ScoringScale) -> None:
        # base 2 + 2 per missing trick x 2 = 6, paid by each declarer.
        result = deltas(ContractKey.ALLIANCE, 6, schaal_a)
        assert result[Seat(0)] == -6
        assert result[Seat(2)] == 6

    def test_misere_made_pays_each_opponent(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.MISERE, 0, schaal_a)
        assert result[Seat(0)] == 15  # 3 x 5
        assert result[Seat(1)] == -5

    def test_solo_slim_made(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.SOLO_SLIM, 13, schaal_a)
        assert result[Seat(0)] == 60  # 3 x 20
        assert result[Seat(1)] == -20

    def test_troel_made(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.TROEL, 8, schaal_a)
        assert result[Seat(0)] == 4
        assert result[Seat(2)] == -4


class TestSchaalB:
    """Grote schaal: the tabulated value is the total, split over the opponents."""

    def test_misere_made(self, schaal_b: ScoringScale) -> None:
        # The scale lists 21 as the declarer's total; the three defenders
        # split it, unlike Schaal A where each would pay 21.
        result = deltas(ContractKey.MISERE, 0, schaal_b)
        assert result[Seat(0)] == 21
        assert result[Seat(1)] == -7
        assert result[Seat(2)] == -7
        assert result[Seat(3)] == -7

    def test_solo_slim_made(self, schaal_b: ScoringScale) -> None:
        result = deltas(ContractKey.SOLO_SLIM, 13, schaal_b)
        assert result[Seat(0)] == 90
        assert result[Seat(1)] == -30

    def test_alone_all_thirteen(self, schaal_b: ScoringScale) -> None:
        result = deltas(ContractKey.ALONE, 13, schaal_b, required=5)
        assert result[Seat(0)] == 60
        assert result[Seat(1)] == -20


class TestJwiesV0:
    """The values from the old controller.ini, now actually applied."""

    def test_fractional_overtricks(self, jwies_v0_scale: ScoringScale) -> None:
        # base 1, +0.5 per overtrick, 10 tricks on an 8-trick contract.
        result = deltas(ContractKey.ALLIANCE, 10, jwies_v0_scale)
        assert result[Seat(0)] == Decimal("2.0")

    def test_losing_is_double(self, jwies_v0_scale: ScoringScale) -> None:
        # One trick short: (1 base + 1 per missing trick) x 2 = 4.
        result = deltas(ContractKey.ALLIANCE, 7, jwies_v0_scale)
        assert result[Seat(0)] == -4

    def test_solo_slim_is_worth_forty_per_opponent(self, jwies_v0_scale: ScoringScale) -> None:
        result = deltas(ContractKey.SOLO_SLIM, 13, jwies_v0_scale)
        assert result[Seat(0)] == 120
        assert result[Seat(1)] == -40


class TestProperties:
    @pytest.mark.parametrize("key", sorted(CONTRACT_CATALOG))
    @pytest.mark.parametrize("tricks", range(14))
    def test_every_round_is_zero_sum(
        self, key: ContractKey, tricks: int, schaal_a: ScoringScale
    ) -> None:
        if not CONTRACT_CATALOG[key].supported or key.value not in schaal_a.contracts:
            pytest.skip("contract niet actief in deze schaal")
        result = deltas(key, tricks, schaal_a)
        assert sum(result.values()) == 0

    def test_multiplier_doubles_everything(self, schaal_a: ScoringScale) -> None:
        plain = score_round(
            RoundResult(contract=contract(ContractKey.MISERE), tricks_made=0), schaal_a
        )
        doubled = score_round(
            RoundResult(
                contract=contract(ContractKey.MISERE),
                tricks_made=0,
                multiplier=Decimal(2),
            ),
            schaal_a,
        )
        assert doubled[Seat(0)] == plain[Seat(0)] * 2

    def test_a_misere_is_down_as_soon_as_it_takes_one_trick(self, schaal_a: ScoringScale) -> None:
        result = deltas(ContractKey.MISERE, 1, schaal_a)
        assert result[Seat(0)] < 0
