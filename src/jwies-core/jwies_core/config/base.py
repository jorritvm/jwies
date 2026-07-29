"""Shared base model for every YAML-backed settings model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["SCHEMA_VERSION", "DutchModel"]

SCHEMA_VERSION = 1


class DutchModel(BaseModel):
    """Immutable settings model with Dutch YAML keys and strict validation.

    ``populate_by_name`` lets tests and code construct models with the English
    field names while YAML files use the Dutch aliases.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )
