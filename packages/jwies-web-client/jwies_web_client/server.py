"""A small dedicated webserver for the browser client.

Deliberately separate from ``jwies-server``: this process only hands out files.
It has no idea what a trick is, holds no state, and keeps running when the game
server is down or being restarted. Players then still get the page - it will
simply tell them it cannot reach the game.

It also serves the card deck - ``static/assets/svg-cards.svg``, so it is just
one more static file - which means a browser never needs to talk to the game
server for anything but the websocket.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from jwies_web_client import STATIC, __version__

__all__ = ["create_app"]


def create_app(game_server_url: str | None = None) -> Starlette:
    """Build the static-file app.

    ``game_server_url`` is handed to the browser through ``/config.json``. Leave
    it empty and the page falls back to the same host it was loaded from, which
    is what you want when a reverse proxy puts both behind one address.
    """

    async def config(_request: Any) -> JSONResponse:
        # The browser reads this at startup to learn where the game lives.
        return JSONResponse(
            {"game_server_url": game_server_url or "", "version": __version__}
        )

    async def healthz(_request: Any) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__, "role": "web-client"})

    return Starlette(
        routes=[
            Route("/config.json", config),
            Route("/healthz", healthz),
            # Last, because it matches everything: the page, the css, the js and
            # assets/svg-cards.svg all come out of this one directory.
            Mount("/", app=StaticFiles(directory=str(STATIC), html=True), name="web"),
        ]
    )


def write_config_file(target: Path, game_server_url: str) -> None:
    """Write a config.json next to the static files.

    Only needed when you serve the folder with something else - nginx, Caddy,
    GitHub Pages - instead of running ``jwies-web``.
    """
    target.write_text(
        json.dumps({"game_server_url": game_server_url}, indent=2) + "\n",
        encoding="utf-8",
    )
