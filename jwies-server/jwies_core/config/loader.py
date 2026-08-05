"""YAML loading with Dutch error reporting.

A game host edits these files by hand, so a pydantic stack trace is useless to
them. ``ConfigError`` renders validation failures as a short Dutch list naming
the offending key and what was wrong with it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from jwies_core.config.ruleset import Ruleset
from jwies_core.config.scoring_scale import ScoringScale

__all__ = [
    "ConfigError",
    "describe_ruleset",
    "describe_scoring_scale",
    "load_ruleset",
    "load_scoring_scale",
    "parse_model",
]

ModelT = TypeVar("ModelT", bound=BaseModel)


class ConfigError(Exception):
    """A settings file could not be read or validated. Message is Dutch."""


def _format_validation_error(what: str, source: str, error: ValidationError) -> str:
    lines = [f"Fout in {what} '{source}':"]
    for detail in error.errors():
        location = ".".join(str(part) for part in detail["loc"]) or "(bestand)"
        message = detail["msg"]
        if detail["type"] == "extra_forbidden":
            message = "onbekende instelling (typfout?)"
        elif detail["type"] == "missing":
            message = "deze instelling ontbreekt"
        elif detail["type"] == "enum":
            expected = detail.get("ctx", {}).get("expected", "")
            message = f"onbekende waarde; toegelaten: {expected}"
        message = message.removeprefix("Value error, ")
        lines.append(f"  - {location}: {message}")
    return "\n".join(lines)


def parse_model[ModelT: BaseModel](
    model: type[ModelT], data: Any, *, what: str, source: str
) -> ModelT:
    """Validate already-parsed data into ``model``, reporting errors in Dutch."""
    if not isinstance(data, dict):
        raise ConfigError(f"Fout in {what} '{source}': het bestand bevat geen instellingen.")
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise ConfigError(_format_validation_error(what, source, error)) from error


def _load_yaml(path: Path, *, what: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"Kan {what} '{path}' niet lezen: {error}") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"Fout in {what} '{path}': ongeldige YAML.\n{error}") from error


def load_ruleset(path: str | Path) -> Ruleset:
    """Load and validate a ruleset YAML file."""
    path = Path(path)
    return parse_model(
        Ruleset, _load_yaml(path, what="regelset"), what="regelset", source=str(path)
    )


def load_scoring_scale(path: str | Path) -> ScoringScale:
    """Load and validate a scoring scale YAML file."""
    path = Path(path)
    return parse_model(
        ScoringScale,
        _load_yaml(path, what="puntenschaal"),
        what="puntenschaal",
        source=str(path),
    )


def _describe(model: BaseModel, indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    for name, field in type(model).model_fields.items():
        alias = field.alias or name
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            lines.append(f"{pad}{alias}:")
            lines.extend(_describe(value, indent + 1))
            continue
        if isinstance(value, list):
            rendered = ", ".join(str(getattr(item, "value", item)) for item in value) or "-"
        else:
            rendered = str(getattr(value, "value", value))
        lines.append(f"{pad}{alias}: {rendered}")
    return lines


def describe_ruleset(ruleset: Ruleset) -> str:
    """Render a ruleset as Dutch plain text for the ``!ruleset`` chat command."""
    header = f"Regelset: {ruleset.name}"
    return "\n".join([header, *_describe(ruleset)])


def describe_scoring_scale(scale: ScoringScale) -> str:
    """Render a scoring scale as a Dutch table for the ``!counting`` chat command.

    The columns below are 52 characters wide in total, which the Qt client sizes
    its chat pane on (``CHAT_TABLE_COLUMNS``). Widen them and the rows wrap.
    """
    payment = (
        "elke tegenstander betaalt het volledige bedrag"
        if scale.solo_payment.value == "per_tegenstander"
        else "het bedrag wordt over de tegenstanders verdeeld"
    )
    lines = [
        f"Puntentelling: {scale.name}",
        f"Bij een speler tegen drie: {payment}.",
        f"Verliezen is dubbel: {'ja' if scale.losing_is_double else 'nee'}.",
        f"Iedereen past verdubbelt de volgende ronde: "
        f"{'ja' if scale.all_passed_doubles else 'nee'}.",
        "",
        f"{'contract':<18}{'basis':>7}{'overslag':>10}{'tekort':>8}{'alle 13':>9}",
    ]
    for key, score in scale.contracts.items():
        all_thirteen = "-" if score.all_thirteen is None else f"{score.all_thirteen:g}"
        lines.append(
            f"{key:<18}{score.base:>7g}{score.per_overtrick:>10g}"
            f"{score.undertrick_value:>8g}{all_thirteen:>9}"
        )
    return "\n".join(lines)
