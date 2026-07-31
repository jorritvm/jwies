"""The Dutch text catalog.

Every player-visible sentence the server produces comes from here. Only
``presenter.py`` and ``chat.py`` are allowed to call ``render``; a test asserts
that every key used in the code exists in ``texts/nl.yaml`` and that no key in
the file is unused.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

__all__ = ["MissingTextError", "TextCatalog"]


class MissingTextError(KeyError):
    """A text key was requested that the catalog does not define."""


class TextCatalog:
    """Maps keys like ``bid.ask`` to Dutch sentences with ``{placeholders}``."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    @classmethod
    def load(cls, path: str | Path | None = None) -> TextCatalog:
        """Load the catalog, from ``path`` if given, else the bundled Dutch one."""
        if path is None:
            raw = (files("jwies_server") / "texts" / "nl.yaml").read_text(encoding="utf-8")
        else:
            raw = Path(path).read_text(encoding="utf-8")
        data: Any = yaml.safe_load(raw)
        if not isinstance(data, dict):
            raise ValueError("de tekstcatalogus bevat geen sleutel/waarde-paren")
        return cls({str(key): str(value) for key, value in data.items()})

    def __contains__(self, key: str) -> bool:
        return key in self._mapping

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(self._mapping)

    def render(self, key: str, /, **kwargs: object) -> str:
        """Render a Dutch sentence. Unknown keys fail loudly rather than silently."""
        try:
            template = self._mapping[key]
        except KeyError:
            raise MissingTextError(f"onbekende tekstsleutel: {key}") from None
        try:
            return template.format(**kwargs)
        except KeyError as error:
            raise MissingTextError(f"tekstsleutel '{key}' mist invulveld {error}") from None
