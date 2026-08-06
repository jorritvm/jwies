"""Point counting against the two published scales.

The expected values come straight from docs/game/rules.md sections 7.2 and 7.3.
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


class TestTheSoloContractsCostAFlatAmountWhenTheyFail:
    """Section 7.2 gives one "Mislukt" figure for these, not a per-trick rate.

    Only the duo contracts (vragen & meegaan, alleen gaan, troel) are charged
    per missing trick. Getting this wrong is expensive in the literal sense: a
    solo slim that drops five tricks once cost 120 a head instead of 20.
    """

    @pytest.mark.parametrize("tricks", [0, 5, 8, 12])
    def test_a_failed_solo_slim_costs_twenty_however_far_down(
        self, tricks: int, schaal_a: ScoringScale
    ) -> None:
        result = deltas(ContractKey.SOLO_SLIM, tricks, schaal_a)
        assert result[Seat(1)] == 20, "elke tegenstander krijgt de vaste 20"
        assert result[Seat(0)] == -60  # de "-60" van de kolom Mislukt

    @pytest.mark.parametrize("tricks", [1, 4, 13])
    def test_a_failed_misere_costs_five_however_many_tricks_it_took(
        self, tricks: int, schaal_a: ScoringScale
    ) -> None:
        result = deltas(ContractKey.MISERE, tricks, schaal_a)
        assert result[Seat(1)] == 5
        assert result[Seat(0)] == -15

    @pytest.mark.parametrize("tricks", [0, 4, 8])
    def test_a_failed_abondance_costs_five(self, tricks: int, schaal_a: ScoringScale) -> None:
        assert deltas(ContractKey.ABONDANCE_9, tricks, schaal_a)[Seat(1)] == 5

    def test_a_failed_misere_ouverte_costs_thirty_over_the_table(
        self, schaal_a: ScoringScale
    ) -> None:
        result = deltas(ContractKey.MISERE_OUVERTE, 3, schaal_a)
        assert result[Seat(1)] == 10
        assert result[Seat(0)] == -30  # de "-30" van de kolom Mislukt

    def test_the_duo_contracts_are_still_charged_per_trick(self, schaal_a: ScoringScale) -> None:
        """The other half of the rule, so a blanket fix would fail here."""
        assert deltas(ContractKey.ALLIANCE, 6, schaal_a)[Seat(0)] == -6
        assert deltas(ContractKey.ALLIANCE, 5, schaal_a)[Seat(0)] == -8


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

    @pytest.mark.parametrize("tricks", [0, 5, 12])
    def test_a_failed_solo_slim_costs_a_flat_ninety(
        self, tricks: int, schaal_b: ScoringScale
    ) -> None:
        """Flat on this scale too - only the split across seats differs."""
        assert deltas(ContractKey.SOLO_SLIM, tricks, schaal_b)[Seat(0)] == -90


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
