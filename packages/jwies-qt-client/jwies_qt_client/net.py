"""Websocket connection to the server.

Uses ``QWebSocket`` from PyQt6, which ships with PyQt: that avoids bridging an
asyncio websocket library into the Qt event loop, and avoids a second event
loop entirely.

Reconnects with exponential backoff and re-presents the same username plus
resume token, which is what binds the player back to their seat.
"""

from __future__ import annotations

import json
import logging

from jwies_protocol import PROTOCOL_VERSION
from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtWebSockets import QWebSocket

__all__ = ["ServerConnection"]

log = logging.getLogger(__name__)

INITIAL_BACKOFF_MS = 1000
MAX_BACKOFF_MS = 30000


class ServerConnection(QObject):
    """Speaks JSON envelopes with the server and emits one signal per message."""

    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    connection_error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.socket = QWebSocket()
        self.url = ""
        self.username = ""
        self.resume_token: str | None = None
        self._counter = 0
        self._backoff = INITIAL_BACKOFF_MS
        self._wanted = False
        self._last_seq = 0

        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.textMessageReceived.connect(self._on_text)
        self.socket.errorOccurred.connect(self._on_error)

    # --- lifecycle ---------------------------------------------------------

    def connect_to(self, url: str, username: str, resume_token: str | None = None) -> None:
        self.url = url
        self.username = username
        self.resume_token = resume_token
        self._wanted = True
        self._backoff = INITIAL_BACKOFF_MS
        self.socket.open(QUrl(url))

    def close(self) -> None:
        self._wanted = False
        self.socket.close()

    def _on_connected(self) -> None:
        self._backoff = INITIAL_BACKOFF_MS
        self._last_seq = 0
        self.send(
            "hello",
            username=self.username,
            client="qt",
            client_version="1",
            resume_token=self.resume_token,
        )
        self.connected.emit()

    def _on_disconnected(self) -> None:
        self.disconnected.emit()
        if self._wanted:
            QTimer.singleShot(self._backoff, self._retry)
            self._backoff = min(self._backoff * 2, MAX_BACKOFF_MS)

    def _retry(self) -> None:
        if self._wanted:
            self.socket.open(QUrl(self.url))

    def _on_error(self, _error: object) -> None:
        self.connection_error.emit(self.socket.errorString())

    # --- messages ----------------------------------------------------------

    def _on_text(self, raw: str) -> None:
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("onleesbaar bericht ontvangen")
            return

        sequence = envelope.get("seq", 0)
        if sequence and self._last_seq and sequence > self._last_seq + 1:
            # We missed something; ask for a fresh snapshot rather than drift.
            self.send("request_snapshot")
        if sequence:
            self._last_seq = sequence

        message = envelope.get("msg")
        if not isinstance(message, dict):
            return
        if message.get("type") == "hello_ok":
            self.resume_token = message.get("resume_token")
        self.message_received.emit(message)

    def send(self, message_type: str, **fields: object) -> None:
        if self.socket.state().value != 3:  # QAbstractSocket.SocketState.ConnectedState
            return
        self._counter += 1
        payload = {
            "v": PROTOCOL_VERSION,
            "id": str(self._counter),
            "msg": {"type": message_type, **fields},
        }
        self.socket.sendTextMessage(json.dumps(payload))
