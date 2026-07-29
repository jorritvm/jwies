"""Configuration models.

Field names are English (the codebase language); the YAML keys a game host
edits are Dutch, supplied as pydantic aliases. ``extra="forbid"`` turns a typo
in a settings file into a startup error instead of a silently ignored rule.
"""

from jwies_core.config.loader import (
    ConfigError,
    describe_ruleset,
    describe_scoring_scale,
    load_ruleset,
    load_scoring_scale,
)
from jwies_core.config.ruleset import AllPassedRule, DealSettings, Ruleset
from jwies_core.config.scoring_scale import ContractScore, ScoringScale, SoloPayment

__all__ = [
    "AllPassedRule",
    "ConfigError",
    "ContractScore",
    "DealSettings",
    "Ruleset",
    "ScoringScale",
    "SoloPayment",
    "describe_ruleset",
    "describe_scoring_scale",
    "load_ruleset",
    "load_scoring_scale",
]
