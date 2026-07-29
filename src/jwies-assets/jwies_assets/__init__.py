"""Shared graphical assets for jwies.

Assets are resolved with ``importlib.resources`` so they keep working from an
installed wheel or a Docker image, unlike the old ``paths.py`` approach which
walked up from ``__file__`` to a project root that only exists in a checkout.
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

__all__ = ["CARD_DECK_SVG", "asset_path", "icon_path", "read_card_deck_svg"]

CARD_DECK_SVG = "svg-cards.svg"


def asset_path(name: str) -> Traversable:
    """Return a traversable handle to a top-level asset."""
    return files(__name__) / name


def icon_path(name: str) -> Traversable:
    """Return a traversable handle to an icon inside ``icons/``."""
    return files(__name__) / "icons" / name


def read_card_deck_svg() -> str:
    """Return the SVG-cards 2.0.1 sheet as text."""
    return asset_path(CARD_DECK_SVG).read_text(encoding="utf-8")
