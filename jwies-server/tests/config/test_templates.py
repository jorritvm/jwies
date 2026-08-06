"""Every shipped template must load, and says what it means when it does not."""

from __future__ import annotations

from pathlib import Path

import pytest

from jwies_core.config import ConfigError, load_ruleset, load_scoring_scale
from jwies_core.config.ruleset import AllPassedRule
from jwies_core.config.scoring_scale import SoloPayment

TEMPLATES = Path(__file__).resolve().parents[3] / "config"
RULESETS = sorted((TEMPLATES / "ruleset").glob("*.yaml"))
SCALES = sorted((TEMPLATES / "scoring").glob("*.yaml"))


def test_templates_are_present() -> None:
    assert RULESETS, "geen regelset-templates gevonden"
    assert SCALES, "geen puntenschaal-templates gevonden"


@pytest.mark.parametrize("path", RULESETS, ids=lambda p: p.name)
def test_every_ruleset_template_validates(path: Path) -> None:
    ruleset = load_ruleset(path)
    assert ruleset.name
    assert sum(ruleset.deal.packets) == 13


@pytest.mark.parametrize("path", SCALES, ids=lambda p: p.name)
def test_every_scoring_template_validates(path: Path) -> None:
    scale = load_scoring_scale(path)
    assert scale.name
    assert scale.contracts


def test_the_two_published_scales_differ_only_structurally_in_payment() -> None:
    schaal_a = load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")
    schaal_b = load_scoring_scale(TEMPLATES / "scoring" / "sporza.yaml")
    assert schaal_a.solo_payment is SoloPayment.PER_OPPONENT
    assert schaal_b.solo_payment is SoloPayment.SHARED
    assert schaal_a.contracts.keys() == schaal_b.contracts.keys()


def test_klassiek_uses_the_traditional_four_four_five_deal() -> None:
    ruleset = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
    assert ruleset.deal.packets == [4, 4, 5]
    assert ruleset.bidding.all_passed is AllPassedRule.NEXT_ROUND_DOUBLE


# --- error reporting ---------------------------------------------------------


def test_unknown_setting_is_reported_in_dutch(tmp_path: Path) -> None:
    bad = tmp_path / "kapot.yaml"
    bad.write_text(
        "schema_versie: 1\nnaam: test\n"
        "delen: {pakjes: [4, 4, 5]}\n"
        "bieden: {volgorde: [alliance], pikkolo: true}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_ruleset(bad)
    message = str(excinfo.value)
    assert "onbekende instelling" in message
    assert "pikkolo" in message


def test_packets_that_do_not_add_up_to_thirteen_are_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "kapot.yaml"
    bad.write_text(
        "schema_versie: 1\nnaam: test\n"
        "delen: {pakjes: [4, 4, 4]}\n"
        "bieden: {volgorde: [alliance]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_ruleset(bad)
    assert "exact 13" in str(excinfo.value)


def test_unsupported_variants_are_rejected_with_a_clear_message(tmp_path: Path) -> None:
    bad = tmp_path / "kapot.yaml"
    bad.write_text(
        "schema_versie: 1\nnaam: test\n"
        "delen: {pakjes: [4, 4, 5]}\n"
        "bieden: {volgorde: [alliance], iedereen_past: dames_rapen}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_ruleset(bad)
    assert "nog niet ondersteund" in str(excinfo.value)


def test_pico_is_known_but_refused_for_now(tmp_path: Path) -> None:
    bad = tmp_path / "kapot.yaml"
    bad.write_text(
        "schema_versie: 1\nnaam: test\n"
        "delen: {pakjes: [4, 4, 5]}\n"
        "bieden: {volgorde: [alliance, pico]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as excinfo:
        load_ruleset(bad)
    assert "pico" in str(excinfo.value)
