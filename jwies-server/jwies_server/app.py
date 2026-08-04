"""The FastAPI application.

This process is the *game* server: a websocket endpoint plus a little
read-only HTTP for health checks and the lobby list.

The browser client is hosted by ``jwies-web`` from the ``jwies-web-client``
package, on its own port. Keeping the two apart means the page still loads
while this server is down or restarting, and that neither has to be redeployed
when the other changes.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from jwies_server import __version__
from jwies_server.config import LoadedConfig
from jwies_server.connection import handle_connection
from jwies_server.lobby_manager import LobbyManager
from jwies_server.protocol import PROTOCOL_VERSION
from jwies_server.sessions import SessionRegistry

__all__ = ["create_app"]

log = logging.getLogger(__name__)

REAP_INTERVAL_SECONDS = 60


def create_app(config: LoadedConfig) -> FastAPI:
    """Build the ASGI app for a loaded configuration."""
    sessions = SessionRegistry()
    lobbies = LobbyManager(config)
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
        await handle_connection(websocket, sessions=sessions, lobbies=lobbies)

    return app


async def _reap_forever(lobbies: LobbyManager) -> None:
    while True:
        await asyncio.sleep(REAP_INTERVAL_SECONDS)
        with contextlib.suppress(Exception):
            await lobbies.reap()
