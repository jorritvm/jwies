"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from jwies_core.config import Ruleset, ScoringScale, load_ruleset, load_scoring_scale

TEMPLATES = Path(__file__).resolve().parents[2] / "config"


@pytest.fixture(scope="session")
def klassiek() -> Ruleset:
    return load_ruleset(TEMPLATES / "ruleset" / "klassiek.yaml")


@pytest.fixture(scope="session")
def jwies_v0_ruleset() -> Ruleset:
    return load_ruleset(TEMPLATES / "ruleset" / "jwies_v0.yaml")


@pytest.fixture(scope="session")
def schaal_a() -> ScoringScale:
    return load_scoring_scale(TEMPLATES / "scoring" / "kaartclubs.yaml")


@pytest.fixture(scope="session")
def schaal_b() -> ScoringScale:
    return load_scoring_scale(TEMPLATES / "scoring" / "sporza.yaml")


@pytest.fixture(scope="session")
def jwies_v0_scale() -> ScoringScale:
    return load_scoring_scale(TEMPLATES / "scoring" / "jwies_v0.yaml")
