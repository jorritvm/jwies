"""A real server on a real port, plus a scripted websocket client."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
import uvicorn
import websockets
from jwies_server.app import create_app
from jwies_server.config import load_server_config

TEMPLATES = Path(__file__).resolve().parents[2] / "templates"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="session")
def fast_config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A server config whose ruleset has no pause between tricks.

    The shipped templates linger two seconds on every trick so players can see
    it, which would make the end-to-end suite spend most of its time asleep.
    Generating a config here also exercises the real loading path.
    """
    directory = tmp_path_factory.mktemp("config")
    ruleset = (TEMPLATES / "ruleset" / "klassiek.yaml").read_text(encoding="utf-8")
    ruleset = ruleset.replace("pauze_na_slag_seconden: 2", "pauze_na_slag_seconden: 0")
    assert "pauze_na_slag_seconden: 0" in ruleset, "pauze-instelling niet gevonden"
    (directory / "snel.yaml").write_text(ruleset, encoding="utf-8")

    server_yaml = (TEMPLATES / "server.yaml").read_text(encoding="utf-8")
    server_yaml = server_yaml.replace(
        '  klassiek: "../templates/ruleset/klassiek.yaml"', '  klassiek: "snel.yaml"'
    )
    server_yaml = server_yaml.replace(
        '  jwies_v0: "../templates/ruleset/jwies_v0.yaml"',
        f'  jwies_v0: "{(TEMPLATES / "ruleset" / "jwies_v0.yaml").as_posix()}"',
    )
    for name in ("schaal_a", "schaal_b", "jwies_v0"):
        server_yaml = server_yaml.replace(
            f'  {name}: "../templates/scoring/{name}.yaml"',
            f'  {name}: "{(TEMPLATES / "scoring" / f"{name}.yaml").as_posix()}"',
        )
    (directory / "server.yaml").write_text(server_yaml, encoding="utf-8")
    return directory


@pytest.fixture
async def server(fast_config_dir: Path) -> AsyncIterator[str]:
    """Run the real app on a free port; yields the websocket URL."""
    config = load_server_config(fast_config_dir / "server.yaml")
    app = create_app(config)
    port = free_port()
    uvicorn_config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"
    )
    server_instance = uvicorn.Server(uvicorn_config)
    task = asyncio.create_task(server_instance.serve())

    for _ in range(200):
        if server_instance.started:
            break
        await asyncio.sleep(0.02)
    else:  # pragma: no cover
        raise RuntimeError("server kwam niet op tijd omhoog")

    try:
        yield f"ws://127.0.0.1:{port}/ws"
    finally:
        server_instance.should_exit = True
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=5)


class ScriptedClient:
    """A minimal client that speaks raw JSON, exactly like the browser does.

    It deliberately does not import pydantic models: if this works, the wire
    format is genuinely language-agnostic.
    """

    def __init__(self, url: str, username: str) -> None:
        self.url = url
        self.username = username
        self.socket: Any = None
        self.received: list[dict[str, Any]] = []
        self.hand: list[str] = []
        self.resume_token: str | None = None
        self.seat: int | None = None
        self._counter = 0

    async def __aenter__(self) -> ScriptedClient:
        self.socket = await websockets.connect(self.url)
        await self.send("hello", username=self.username, client="web")
        await self.wait_for("hello_ok")
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self.socket is not None:
            await self.socket.close()
            self.socket = None

    async def send(self, message_type: str, **fields: Any) -> None:
        self._counter += 1
        payload = {"v": 1, "id": str(self._counter), "msg": {"type": message_type, **fields}}
        await self.socket.send(json.dumps(payload))

    async def _recv(self, timeout: float = 5.0) -> dict[str, Any]:
        raw = await asyncio.wait_for(self.socket.recv(), timeout=timeout)
        envelope = json.loads(raw)
        message = envelope["msg"]
        self.received.append(message)
        if message["type"] == "hello_ok":
            self.resume_token = message["resume_token"]
        elif message["type"] == "hand_dealt":
            self.hand = list(message["cards"])
        elif message["type"] == "game_started":
            self.seat = message["your_seat"]
        return message

    async def wait_for(
        self,
        message_type: str,
        *,
        timeout: float = 10.0,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any]:
        async def hunt() -> dict[str, Any]:
            while True:
                message = await self._recv(timeout=timeout)
                if message["type"] == message_type and (predicate is None or predicate(message)):
                    return message

        return await asyncio.wait_for(hunt(), timeout=timeout)

    def seen(self, message_type: str) -> list[dict[str, Any]]:
        return [message for message in self.received if message["type"] == message_type]

    async def drain(self, seconds: float = 0.3) -> None:
        """Read whatever is pending without waiting for anything specific."""
        with contextlib.suppress(asyncio.TimeoutError):
            while True:
                await self._recv(timeout=seconds)


async def answer_prompt(client: ScriptedClient, prompt: dict[str, Any]) -> None:
    """A deterministic policy: never needs to know the rules."""
    kind = prompt["kind"]
    if kind == "shuffle":
        await client.send("answer_shuffle", shuffle=False)
    elif kind == "cut":
        await client.send("answer_cut", count=prompt["cut_minimum"])
    elif kind == "bid":
        options = prompt["bid_options"]
        choice = (
            next(
                (option for option in options if option["type"] == "ask"),
                None,
            )
            or next(
                (option for option in options if option["type"] == "alone"),
                None,
            )
            or next(option for option in options if option["type"] == "pass")
        )
        await client.send("place_bid", bid=choice)
    elif kind == "play":
        await client.send("play_card", card=prompt["legal_cards"][0])


async def play_until(
    clients: list[ScriptedClient],
    stop: Callable[[dict[str, Any], ScriptedClient], bool],
    *,
    timeout: float = 60.0,
) -> None:
    """Drive all clients concurrently until ``stop`` says so."""
    done = asyncio.Event()

    async def pump(client: ScriptedClient) -> None:
        while not done.is_set():
            try:
                message = await client._recv(timeout=1.0)
            except TimeoutError:
                continue
            if message["type"] == "prompt":
                await answer_prompt(client, message["prompt"])
            if stop(message, client):
                done.set()

    tasks = [asyncio.create_task(pump(client)) for client in clients]
    try:
        await asyncio.wait_for(done.wait(), timeout=timeout)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
