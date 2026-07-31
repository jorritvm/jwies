"""Chat commands.

Commands register themselves through a decorator together with their own help
line, so ``!help`` is generated from the registry and can never drift from what
actually exists.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jwies_core.config import describe_ruleset, describe_scoring_scale

from jwies_server.protocol import PROTOCOL_VERSION

if TYPE_CHECKING:
    from jwies_server.lobby import LobbyRuntime
    from jwies_server.sessions import Session

__all__ = ["COMMANDS", "ChatContext", "handle_chat_command", "is_command"]

COMMAND_PREFIX = "!"

NEEDS_LOBBY = "Dat commando werkt enkel binnen een lobby."


@dataclass
class ChatContext:
    """Everything a command may look at."""

    lobby: LobbyRuntime | None
    session: Session
    argument: str = ""


CommandHandler = Callable[[ChatContext], list[str]]

COMMANDS: dict[str, tuple[CommandHandler, str]] = {}


def command(name: str, help_line: str) -> Callable[[CommandHandler], CommandHandler]:
    """Register a chat command together with its line in ``!help``."""

    def register(handler: CommandHandler) -> CommandHandler:
        COMMANDS[name] = (handler, help_line)
        return handler

    return register


def is_command(text: str) -> bool:
    return text.startswith(COMMAND_PREFIX)


@command("help", "!help     - toon deze lijst")
def _help(context: ChatContext) -> list[str]:
    return ["Beschikbare commando's:", *(COMMANDS[name][1] for name in sorted(COMMANDS))]


@command("ruleset", "!ruleset  - toon de spelregels die in deze lobby gelden")
def _ruleset(context: ChatContext) -> list[str]:
    if context.lobby is None:
        return [NEEDS_LOBBY]
    return describe_ruleset(context.lobby.ruleset).splitlines()


@command("counting", "!counting - toon hoe de punten geteld worden")
def _counting(context: ChatContext) -> list[str]:
    if context.lobby is None:
        return [NEEDS_LOBBY]
    return describe_scoring_scale(context.lobby.scoring).splitlines()


@command("score", "!score    - toon de huidige stand")
def _score(context: ChatContext) -> list[str]:
    lobby = context.lobby
    if lobby is None:
        return [NEEDS_LOBBY]
    if lobby.engine is None:
        return ["Er is nog geen spel bezig, dus er is nog geen stand."]

    from jwies_core.seats import Seat

    from jwies_server.presenter import _decimal

    rows = [
        (member.username, lobby.engine.totals.get(Seat(member.seat), 0))
        for member in lobby.members.values()
        if member.seat is not None
    ]
    rows.sort(key=lambda row: row[1], reverse=True)
    return [
        "Huidige stand:",
        *(
            f"  {username}: {_decimal(total)}"  # type: ignore[arg-type]
            for username, total in rows
        ),
    ]


@command("seats", "!seats    - toon wie waar zit")
def _seats(context: ChatContext) -> list[str]:
    lobby = context.lobby
    if lobby is None:
        return [NEEDS_LOBBY]
    lines = ["Aan tafel:"]
    for seat in range(4):
        member = lobby.member_at(seat)
        if member is None:
            name, status = "leeg", ""
        else:
            name = member.username
            status = "" if member.connected else " (offline)"
        lines.append(f"  stoel {seat + 1}: {name}{status}")
    return lines


@command("version", "!version  - toon de serverversie")
def _version(context: ChatContext) -> list[str]:
    from jwies_server import __version__

    return [f"jwies-server {__version__}, protocol versie {PROTOCOL_VERSION}."]


def handle_chat_command(text: str, context: ChatContext) -> list[str]:
    """Run a ``!command``. Returns the Dutch lines to send back privately."""
    body = text[len(COMMAND_PREFIX) :].strip()
    name, _, argument = body.partition(" ")
    name = name.lower()

    entry = COMMANDS.get(name)
    if entry is None:
        return [f"Onbekend commando '{name}'. Typ !help voor de lijst."]

    handler, _help_line = entry
    context.argument = argument.strip()
    return handler(context)
