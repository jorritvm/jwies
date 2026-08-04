"""The game server hands out no files and knows nothing about the web client.

The web client's own half of this split - that it keeps serving the page while
the game is down - is tested in jwies-web-client's own test suite instead;
this file only needs the game server, never jwies-web-client.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jwies_server.app import create_app
from jwies_server.config import load_server_config

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT.parent / "config"


@pytest.fixture(scope="module")
def game() -> TestClient:
    """The game server. Serves no HTML at all."""
    return TestClient(create_app(load_server_config(TEMPLATES / "server.yaml")))


def test_the_game_server_serves_no_web_client(game: TestClient) -> None:
    """The whole point of the split: the game server hands out no files."""
    for path in ("/", "/index.html", "/js/main.js", "/css/base.css"):
        assert game.get(path).status_code == 404, f"{path} wordt toch geserveerd"


def test_the_game_server_still_answers_its_own_endpoints(game: TestClient) -> None:
    payload = game.get("/healthz").json()
    assert payload["status"] == "ok"
    assert payload["protocol"] == 2
    assert game.get("/api/lobbies").json() == []


def test_the_game_server_does_not_depend_on_the_web_client() -> None:
    manifest = ROOT / "pyproject.toml"
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    dependencies = " ".join(data["project"]["dependencies"])
    assert "jwies-web-client" not in dependencies
