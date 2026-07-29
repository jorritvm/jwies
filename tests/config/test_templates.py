"""Every shipped template must load, and every key must be documented."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jwies_core.config import ConfigError, load_ruleset, load_scoring_scale
from jwies_core.config.ruleset import AllPassedRule
from jwies_core.config.scoring_scale import SoloPayment

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
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


def test_jwies_v0_reproduces_the_old_controller_ini() -> None:
    ruleset = load_ruleset(TEMPLATES / "ruleset" / "jwies_v0.yaml")
    scale = load_scoring_scale(TEMPLATES / "scoring" / "jwies_v0.yaml")

    # [deal] section of config/controller.ini
    assert ruleset.deal.packets == [3, 3, 3, 4]
    assert ruleset.deal.dealer_may_shuffle is True
    assert ruleset.deal.cut_minimum == 1
    assert ruleset.deal.cut_maximum == 51

    # [bid] section: only soloslim_beats_trull was True
    assert ruleset.bidding.troel_above_all is True
    assert [key.value for key in ruleset.bidding.troel_beaten_by] == ["solo_slim"]

    # [points] section
    assert ruleset.bidding.troel_tricks == 8
    assert scale.losing_is_double is True
    assert scale.all_passed_doubles is True
    assert scale.contracts["alliance"].base == 1
    assert scale.contracts["alliance"].per_overtrick == pytest.approx(0.5)
    assert scale.contracts["abondance_9"].base == 5
    assert scale.contracts["misere"].base == 5
    assert scale.contracts["misere_ouverte"].base == 10
    assert scale.contracts["solo"].base == 20
    assert scale.contracts["solo_slim"].base == 40


def test_the_two_published_scales_differ_only_structurally_in_payment() -> None:
    schaal_a = load_scoring_scale(TEMPLATES / "scoring" / "schaal_a.yaml")
    schaal_b = load_scoring_scale(TEMPLATES / "scoring" / "schaal_b.yaml")
    assert schaal_a.solo_payment is SoloPayment.PER_OPPONENT
    assert schaal_b.solo_payment is SoloPayment.SHARED
    assert schaal_a.contracts.keys() == schaal_b.contracts.keys()


def test_klassiek_uses_the_traditional_four_four_five_deal() -> None:
    ruleset = load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")
    assert ruleset.deal.packets == [4, 4, 5]
    assert ruleset.bidding.all_passed is AllPassedRule.NEXT_ROUND_DOUBLE


# --- requirement: every setting is explained in the file itself ---------------

KEY_LINE = re.compile(r"^(?P<indent>\s*)(?P<key>[a-z_0-9]+):")

# Maps whose entries all share one value schema. The schema is documented once,
# above the map itself; repeating the same four comments under each of twelve
# contracts would make the file harder to read, not easier. Each *entry* of such
# a map (the contract name, the ruleset name) still needs its own comment.
REPEATED_MAPS = frozenset({"contracten", "regelsets", "puntenschalen"})


def _undocumented_keys(path: Path) -> list[str]:
    """Keys that are not preceded by at least one comment line."""
    lines = path.read_text(encoding="utf-8").splitlines()
    offenders: list[str] = []
    # indent width -> key that opened that block, to spot schema repetition
    open_blocks: dict[int, str] = {}

    for index, line in enumerate(lines):
        match = KEY_LINE.match(line)
        if not match:
            continue
        indent = len(match.group("indent"))
        key = match.group("key")

        open_blocks = {width: name for width, name in open_blocks.items() if width < indent}
        parent = open_blocks.get(max(open_blocks, default=-1)) if open_blocks else None
        grandparent_is_repeated = any(
            name in REPEATED_MAPS for width, name in open_blocks.items() if width < indent
        )
        open_blocks[indent] = key

        # A value inside an entry of a repeated map: schema documented above the map.
        if parent is not None and grandparent_is_repeated and parent not in REPEATED_MAPS:
            continue

        # Walk back over blank lines to the nearest non-blank line.
        previous = index - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        if previous < 0 or not lines[previous].lstrip().startswith("#"):
            offenders.append(f"regel {index + 1}: {key}")
    return offenders


@pytest.mark.parametrize(
    "path",
    [*RULESETS, *SCALES, TEMPLATES / "server.yaml"],
    ids=lambda p: p.name,
)
def test_every_template_key_is_preceded_by_a_comment(path: Path) -> None:
    # Mechanises the requirement that a game host can tune any setting without
    # reading the source: each key explains itself in the file above it.
    offenders = _undocumented_keys(path)
    assert not offenders, f"{path.name} mist uitleg bij: {', '.join(offenders)}"


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
