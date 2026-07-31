"""Creating, joining, listing and reaping lobbies."""

from __future__ import annotations

import itertools
import logging
import time

from jwies_protocol import LobbyStatusCode, LobbySummary

from jwies_server.config import LoadedConfig
from jwies_server.lobby import LobbyRuntime
from jwies_server.sessions import Session
from jwies_server.texts import TextCatalog

__all__ = ["LobbyError", "LobbyManager"]

log = logging.getLogger(__name__)


class LobbyError(Exception):
    """Something a player asked for cannot be done. Message is Dutch."""

    def __init__(self, code: str, text: str) -> None:
        super().__init__(text)
        self.code = code
        self.text = text


class LobbyManager:
    """Owns every lobby on this server."""

    def __init__(self, config: LoadedConfig, catalog: TextCatalog) -> None:
        self.config = config
        self.catalog = catalog
        self.lobbies: dict[str, LobbyRuntime] = {}
        self._ids = itertools.count(1)

    # --- queries -----------------------------------------------------------

    def list_summaries(self) -> tuple[LobbySummary, ...]:
        return tuple(lobby.summary() for lobby in self.lobbies.values())

    def get(self, lobby_id: str) -> LobbyRuntime:
        lobby = self.lobbies.get(lobby_id)
        if lobby is None:
            raise LobbyError("lobby_not_found", self.catalog.render("error.lobby_not_found"))
        return lobby

    def lobby_of(self, session: Session) -> LobbyRuntime | None:
        if session.lobby_id is None:
            return None
        return self.lobbies.get(session.lobby_id)

    # --- commands ----------------------------------------------------------

    def create(
        self,
        session: Session,
        name: str,
        *,
        ruleset: str | None,
        scoring: str | None,
        rng_seed: int | None = None,
    ) -> LobbyRuntime:
        settings = self.config.config
        if len(self.lobbies) >= settings.lobby.maximum:
            raise LobbyError(
                "internal",
                self.catalog.render("error.max_lobbies", maximum=settings.lobby.maximum),
            )
        if any(lobby.name.casefold() == name.casefold() for lobby in self.lobbies.values()):
            raise LobbyError("lobby_exists", self.catalog.render("error.lobby_exists"))

        ruleset_name = ruleset or settings.default_ruleset
        scoring_name = scoring or settings.default_scoring
        if ruleset_name not in self.config.rulesets:
            raise LobbyError(
                "unknown_ruleset",
                self.catalog.render(
                    "error.unknown_ruleset",
                    naam=ruleset_name,
                    beschikbaar=", ".join(sorted(self.config.rulesets)),
                ),
            )
        if scoring_name not in self.config.scorings:
            raise LobbyError(
                "unknown_scoring",
                self.catalog.render(
                    "error.unknown_scoring",
                    naam=scoring_name,
                    beschikbaar=", ".join(sorted(self.config.scorings)),
                ),
            )

        self.leave(session)

        lobby_id = f"lobby-{next(self._ids)}"
        lobby = LobbyRuntime(
            lobby_id,
            name,
            session,
            ruleset=self.config.rulesets[ruleset_name],
            ruleset_name=ruleset_name,
            scoring=self.config.scorings[scoring_name],
            scoring_name=scoring_name,
            catalog=self.catalog,
            rng_seed=rng_seed,
        )
        lobby.start_task()
        self.lobbies[lobby_id] = lobby
        log.info("lobby %s aangemaakt door %s", lobby_id, session.username)
        return lobby

    def join(self, session: Session, lobby_id: str) -> LobbyRuntime:
        lobby = self.get(lobby_id)
        if session.username in lobby.members:
            return lobby
        if not lobby.free_seats():
            raise LobbyError("lobby_full", self.catalog.render("error.lobby_full"))
        self.leave(session)
        lobby.add_member(session)
        log.info("%s komt in lobby %s", session.username, lobby_id)
        return lobby

    def leave(self, session: Session) -> LobbyRuntime | None:
        lobby = self.lobby_of(session)
        if lobby is None:
            return None
        lobby.remove_member(session.username)
        if lobby.is_empty():
            self.lobbies.pop(lobby.id, None)
        return lobby

    async def delete(self, session: Session, lobby_id: str) -> None:
        lobby = self.get(lobby_id)
        # The host may always delete; anyone may clear away an empty lobby.
        if lobby.host_username != session.username and not lobby.is_empty():
            raise LobbyError("not_host", self.catalog.render("error.not_host"))
        for member in list(lobby.members.values()):
            member.session.lobby_id = None
            member.session.seat = None
        await lobby.stop_task()
        self.lobbies.pop(lobby_id, None)
        log.info("lobby %s verwijderd", lobby_id)

    # --- housekeeping ------------------------------------------------------

    async def reap(self) -> int:
        """Drop lobbies nobody has been connected to for a while."""
        cutoff = self.config.config.lobby.reap_after_minutes * 60
        now = time.monotonic()
        removed = 0
        for lobby_id, lobby in list(self.lobbies.items()):
            idle = now - lobby.last_activity
            if lobby.has_connected_players() or idle < cutoff:
                continue
            await lobby.stop_task()
            for member in list(lobby.members.values()):
                member.session.lobby_id = None
                member.session.seat = None
            self.lobbies.pop(lobby_id, None)
            removed += 1
            log.info("lobby %s opgeruimd na %.0f minuten inactiviteit", lobby_id, idle / 60)
        return removed

    async def shutdown(self) -> None:
        for lobby in list(self.lobbies.values()):
            await lobby.stop_task()
        self.lobbies.clear()

    @staticmethod
    def is_startable(lobby: LobbyRuntime) -> bool:
        return (
            lobby.status is LobbyStatusCode.WAITING
            and lobby.engine is None
            and len(lobby.members) == 4
        )
