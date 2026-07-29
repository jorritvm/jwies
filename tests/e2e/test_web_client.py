"""The browser client is served correctly and its assets resolve.

We cannot run a browser here, so this checks the things that would silently
break it: the files being served at all, the card sheet being reachable at the
path the JS fetches, and the SVG element ids the JS builds actually existing in
that sheet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jwies_core.cards import full_deck
from jwies_server.app import create_app
from jwies_server.config import load_server_config

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"
WEB = Path(__file__).resolve().parents[2] / "src" / "jwies-server" / "jwies_server" / "web"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(load_server_config(TEMPLATES / "server.yaml")))


def test_the_index_page_is_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "<title>jwies" in response.text
    assert 'lang="nl"' in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/css/base.css",
        "/css/table.css",
        "/js/main.js",
        "/js/net.js",
        "/js/store.js",
        "/js/table.js",
        "/js/cards.js",
        "/js/labels.js",
    ],
)
def test_every_referenced_file_is_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


def test_the_card_sheet_is_reachable_at_the_path_the_client_fetches(
    client: TestClient,
) -> None:
    # js/cards.js does fetch("/assets/svg-cards.svg")
    response = client.get("/assets/svg-cards.svg")
    assert response.status_code == 200
    assert b"<svg" in response.content


def test_healthz_reports_status(client: TestClient) -> None:
    payload = client.get("/healthz").json()
    assert payload["status"] == "ok"
    assert payload["protocol"] == 1


def test_the_lobby_api_is_readable_without_a_websocket(client: TestClient) -> None:
    assert client.get("/api/lobbies").json() == []


def test_every_card_id_the_client_builds_exists_in_the_sheet() -> None:
    # cards.js maps a code like "10S" to an element id like "10_spade". If the
    # two ever disagree, cards render blank - so check all 52 plus the back.
    sheet = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "jwies-assets"
        / "jwies_assets"
        / "svg-cards.svg"
    ).read_text(encoding="utf-8", errors="ignore")
    ids = set(re.findall(r'id="([^"]+)"', sheet))

    for card in full_deck():
        assert card.svg_element_id in ids, f"{card.code} -> {card.svg_element_id} ontbreekt"
    assert "back" in ids


def test_the_javascript_and_python_agree_on_card_ids() -> None:
    """The JS mapping tables must match the engine's svg_element_id."""
    source = (WEB / "js" / "cards.js").read_text(encoding="utf-8")
    suits = dict(re.findall(r'(\w): "(\w+)"', source.split("SUIT_SVG = {")[1].split("}")[0]))
    ranks = dict(re.findall(r'(\w+): "(\w+)"', source.split("RANK_SVG = {")[1].split("};")[0]))
    for card in full_deck():
        rank_key = card.rank.code
        expected = f"{ranks[rank_key]}_{suits[card.suit.value]}"
        assert expected == card.svg_element_id, f"JS en Python verschillen voor {card.code}"


def test_only_client_chrome_is_translated_in_the_client() -> None:
    """Game sentences must come from the server, not be hard-coded here."""
    labels = (WEB / "js" / "labels.js").read_text(encoding="utf-8")
    # These are server-rendered sentences; finding them in the client would
    # mean the Dutch had been duplicated.
    for forbidden in ("IK GA", "wint de slag", "Contract gehaald"):
        assert forbidden not in labels
