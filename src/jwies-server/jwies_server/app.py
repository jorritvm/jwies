"""The FastAPI application.

One process serves both the browser client and the websocket endpoint, so the
web client needs no separate static server, no CORS configuration, and no
second port through the router.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from importlib.resources import as_file, files
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jwies_protocol import PROTOCOL_VERSION

from jwies_server import __version__
from jwies_server.config import LoadedConfig
from jwies_server.connection import handle_connection
from jwies_server.lobby_manager import LobbyManager
from jwies_server.sessions import SessionRegistry
from jwies_server.texts import TextCatalog

__all__ = ["create_app"]

log = logging.getLogger(__name__)

REAP_INTERVAL_SECONDS = 60


def create_app(config: LoadedConfig, *, catalog: TextCatalog | None = None) -> FastAPI:
    """Build the ASGI app for a loaded configuration."""
    catalog = catalog or TextCatalog.load()
    sessions = SessionRegistry()
    lobbies = LobbyManager(config, catalog)
    started = time.monotonic()

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        reaper = asyncio.create_task(_reap_forever(lobbies), name="lobby-reaper")
        try:
            yield
        finally:
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
            await lobbies.shutdown()

    app = FastAPI(
        title="jwies",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.sessions = sessions
    app.state.lobbies = lobbies
    app.state.catalog = catalog
    app.state.config = config

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": __version__,
                "protocol": PROTOCOL_VERSION,
                "lobbies": len(lobbies.lobbies),
                "uptime_seconds": round(time.monotonic() - started),
            }
        )

    @app.get("/api/lobbies")
    async def api_lobbies() -> JSONResponse:
        return JSONResponse([summary.model_dump() for summary in lobbies.list_summaries()])

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await handle_connection(websocket, sessions=sessions, lobbies=lobbies, catalog=catalog)

    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Serve the card assets and the browser client from this same process.

    Both come from separate packages that hold nothing but files, so they are
    located through ``importlib.resources`` rather than by walking up from
    ``__file__``. That keeps working from an installed wheel or a container
    image.
    """
    with as_file(files("jwies_assets")) as assets_dir:
        if Path(assets_dir).is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

    # The browser client is an optional dependency in practice: a server that
    # only ever talks to PyQt clients does not need it, and should still start.
    try:
        from jwies_web_client import static_root
    except ImportError:  # pragma: no cover - only without the web client
        log.warning(
            "jwies-web-client is niet geinstalleerd; de browserclient wordt niet "
            "aangeboden. De PyQt-client werkt gewoon."
        )
        return

    with as_file(static_root()) as web_dir:
        if Path(web_dir).is_dir():
            app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
        else:  # pragma: no cover - a broken install
            log.warning("webclient niet gevonden op %s", web_dir)


async def _reap_forever(lobbies: LobbyManager) -> None:
    while True:
        await asyncio.sleep(REAP_INTERVAL_SECONDS)
        with contextlib.suppress(Exception):
            await lobbies.reap()
