"""Chat commands.

Commands register themselves through a decorator, so ``!help`` is generated
from the registry and can never drift from what actually exists.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from jwies_core.config import describe_ruleset, describe_scoring_scale
from jwies_protocol import PROTOCOL_VERSION

from jwies_server.texts import TextCatalog

if TYPE_CHECKING:
    from jwies_server.lobby import LobbyRuntime
    from jwies_server.sessions import Session

__all__ = ["COMMANDS", "ChatContext", "handle_chat_command", "is_command"]

COMMAND_PREFIX = "!"


@dataclass
class ChatContext:
    """Everything a command may look at."""

    lobby: LobbyRuntime | None
    session: Session
    catalog: TextCatalog
    argument: str = ""


CommandHandler = Callable[[ChatContext], list[str]]

COMMANDS: dict[str, tuple[CommandHandler, str]] = {}


def command(name: str, help_key: str) -> Callable[[CommandHandler], CommandHandler]:
    """Register a chat command together with the text key describing it."""

    def register(handler: CommandHandler) -> CommandHandler:
        COMMANDS[name] = (handler, help_key)
        return handler

    return register


def is_command(text: str) -> bool:
    return text.startswith(COMMAND_PREFIX)


@command("help", "chat.help.help")
def _help(context: ChatContext) -> list[str]:
    lines = [context.catalog.render("chat.help.header")]
    for name in sorted(COMMANDS):
        _, help_key = COMMANDS[name]
        lines.append(context.catalog.render(help_key))
    return lines


@command("ruleset", "chat.help.ruleset")
def _ruleset(context: ChatContext) -> list[str]:
    if context.lobby is None:
        return [context.catalog.render("chat.needs_lobby")]
    return describe_ruleset(context.lobby.ruleset).splitlines()


@command("counting", "chat.help.counting")
def _counting(context: ChatContext) -> list[str]:
    if context.lobby is None:
        return [context.catalog.render("chat.needs_lobby")]
    return describe_scoring_scale(context.lobby.scoring).splitlines()


@command("score", "chat.help.score")
def _score(context: ChatContext) -> list[str]:
    lobby = context.lobby
    if lobby is None:
        return [context.catalog.render("chat.needs_lobby")]
    if lobby.engine is None:
        return [context.catalog.render("chat.score.no_game")]

    from jwies_core.seats import Seat

    from jwies_server.presenter import _decimal

    rows = [
        (member.username, lobby.engine.totals.get(Seat(member.seat), 0))
        for member in lobby.members.values()
        if member.seat is not None
    ]
    rows.sort(key=lambda row: row[1], reverse=True)
    lines = [context.catalog.render("chat.score.header")]
    for username, total in rows:
        lines.append(
            context.catalog.render(
                "chat.score.line",
                speler=username,
                totaal=_decimal(total),  # type: ignore[arg-type]
            )
        )
    return lines


@command("seats", "chat.help.seats")
def _seats(context: ChatContext) -> list[str]:
    lobby = context.lobby
    if lobby is None:
        return [context.catalog.render("chat.needs_lobby")]
    lines = [context.catalog.render("chat.seats.header")]
    for seat in range(4):
        member = lobby.member_at(seat)
        if member is None:
            name = context.catalog.render("chat.seats.empty")
            status = ""
        else:
            name = member.username
            status = "" if member.connected else context.catalog.render("chat.seats.disconnected")
        lines.append(
            context.catalog.render("chat.seats.line", stoel=seat + 1, speler=name, status=status)
        )
    return lines


@command("version", "chat.help.version")
def _version(context: ChatContext) -> list[str]:
    from jwies_server import __version__

    return [context.catalog.render("chat.version", versie=__version__, protocol=PROTOCOL_VERSION)]


def handle_chat_command(text: str, context: ChatContext) -> list[str]:
    """Run a ``!command``. Returns the Dutch lines to send back privately."""
    body = text[len(COMMAND_PREFIX) :].strip()
    name, _, argument = body.partition(" ")
    name = name.lower()

    entry = COMMANDS.get(name)
    if entry is None:
        return [context.catalog.render("chat.unknown_command", commando=name)]

    handler, _help_key = entry
    context.argument = argument.strip()
    return handler(context)
