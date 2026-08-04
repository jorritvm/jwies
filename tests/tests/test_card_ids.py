"""Each client's own card table must agree with jwies_core's canonical one.

Both clients deliberately keep their own card-code -> SVG-element-id table
instead of depending on jwies_core, so that neither the PyQt client nor the
browser client ever needs the rules engine installed. That means nothing
inside either client's own test suite can catch the two tables drifting apart
- so this project exists specifically to hold the checks that do, with
jwies-core (via jwies-server), jwies-qt-client and jwies-web-client all
installed together.
"""

from __future__ import annotations

import re

import pytest
from jwies_core.cards import full_deck
from jwies_qt_client.cards import svg_element_id
from jwies_web_client import STATIC

WEB = STATIC


@pytest.mark.parametrize("card", full_deck())
def test_the_qt_client_agrees_with_the_engine(card) -> None:
    assert svg_element_id(card.code) == card.svg_element_id


def test_every_card_id_the_browser_client_builds_exists_in_the_sheet() -> None:
    # cards.js maps a code like "10S" to an element id like "10_spade". If the
    # two ever disagree, cards render blank - so check all 52 plus the back.
    sheet = (WEB / "assets" / "svg-cards.svg").read_text(encoding="utf-8", errors="ignore")
    ids = set(re.findall(r'id="([^"]+)"', sheet))

    for card in full_deck():
        assert card.svg_element_id in ids, f"{card.code} -> {card.svg_element_id} ontbreekt"
    assert "back" in ids


def test_the_browser_javascript_and_the_engine_agree_on_card_ids() -> None:
    """The JS mapping tables must match the engine's svg_element_id."""
    source = (WEB / "js" / "cards.js").read_text(encoding="utf-8")
    suits = dict(re.findall(r'(\w): "(\w+)"', source.split("SUIT_SVG = {")[1].split("}")[0]))
    ranks = dict(re.findall(r'(\w+): "(\w+)"', source.split("RANK_SVG = {")[1].split("};")[0]))
    for card in full_deck():
        rank_key = card.rank.code
        expected = f"{ranks[rank_key]}_{suits[card.suit.value]}"
        assert expected == card.svg_element_id, f"JS en Python verschillen voor {card.code}"
