"""Error codes.

Clients switch on the code; the accompanying ``text`` is already Dutch and can
be shown to the player as-is.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ErrorCode"]


class ErrorCode(StrEnum):
    PROTOCOL_VERSION = "protocol_version"
    USERNAME_TAKEN = "username_taken"
    USERNAME_INVALID = "username_invalid"
    NOT_IN_LOBBY = "not_in_lobby"
    LOBBY_FULL = "lobby_full"
    LOBBY_NOT_FOUND = "lobby_not_found"
    LOBBY_EXISTS = "lobby_exists"
    NOT_HOST = "not_host"
    NOT_YOUR_TURN = "not_your_turn"
    ILLEGAL_MOVE = "illegal_move"
    GAME_PAUSED = "game_paused"
    GAME_NOT_RUNNING = "game_not_running"
    UNKNOWN_RULESET = "unknown_ruleset"
    UNKNOWN_SCORING = "unknown_scoring"
    BAD_MESSAGE = "bad_message"
    INTERNAL = "internal"
