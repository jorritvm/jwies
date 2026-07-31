"""Sessions, chat commands, and the Dutch text catalog."""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

import pytest
from jwies_core.config import Ruleset, ScoringScale
from jwies_server.chat import COMMANDS, ChatContext, handle_chat_command, is_command
from jwies_server.sessions import HelloOutcome, SessionRegistry
from jwies_server.texts import MissingTextError, TextCatalog

SERVER_SRC = Path(__file__).resolve().parents[2] / "packages" / "jwies-server" / "jwies_server"


@pytest.fixture(scope="module")
def catalog() -> TextCatalog:
    return TextCatalog.load()


class TestSessions:
    def test_an_unknown_username_creates_a_session(self) -> None:
        registry = SessionRegistry()
        session, outcome = registry.resolve_hello("Jan", None)
        assert outcome is HelloOutcome.NEW
        assert session.resume_token

    def test_a_matching_token_resumes(self) -> None:
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.disconnect()
        again, outcome = registry.resolve_hello("Jan", session.resume_token)
        assert outcome is HelloOutcome.RESUMED
        assert again is session

    def test_a_dead_session_rebinds_without_a_token(self) -> None:
        # The requirement: the username is the key.
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.disconnect()
        again, outcome = registry.resolve_hello("Jan", None)
        assert outcome is HelloOutcome.REBOUND
        assert again is session

    def test_a_live_session_is_defended(self) -> None:
        registry = SessionRegistry()
        session, _ = registry.resolve_hello("Jan", None)
        session.agent = object()  # type: ignore[assignment]
        _, outcome = registry.resolve_hello("Jan", "wrong-token")
        assert outcome is HelloOutcome.TAKEN

    def test_usernames_are_case_insensitively_unique(self) -> None:
        registry = SessionRegistry()
        first, _ = registry.resolve_hello("Jan", None)
        first.disconnect()
        second, outcome = registry.resolve_hello("JAN", None)
        assert second is first
        assert outcome is HelloOutcome.REBOUND

    @pytest.mark.parametrize("name", ["Jan", "Jan-Piet", "speler 1", "a_b", "ab"])
    def test_valid_usernames(self, name: str) -> None:
        assert SessionRegistry.is_valid_username(name)

    @pytest.mark.parametrize("name", ["a", "", "x" * 21, "Jan;drop", "<script>"])
    def test_invalid_usernames(self, name: str) -> None:
        assert not SessionRegistry.is_valid_username(name)


class TestChatCommands:
    def test_command_detection(self) -> None:
        assert is_command("!help")
        assert not is_command("gewoon een zin")

    def test_help_lists_every_registered_command(self, catalog: TextCatalog) -> None:
        context = ChatContext(lobby=None, session=None, catalog=catalog)  # type: ignore[arg-type]
        lines = handle_chat_command("!help", context)
        body = "\n".join(lines)
        for name in COMMANDS:
            assert f"!{name}" in body, f"!{name} ontbreekt in !help"

    def test_unknown_command_is_reported_in_dutch(self, catalog: TextCatalog) -> None:
        context = ChatContext(lobby=None, session=None, catalog=catalog)  # type: ignore[arg-type]
        lines = handle_chat_command("!bestaatniet", context)
        assert "Onbekend commando" in lines[0]

    def test_ruleset_and_counting_render_dutch(
        self, catalog: TextCatalog, klassiek: Ruleset, schaal_a: ScoringScale
    ) -> None:
        class FakeLobby:
            ruleset = klassiek
            scoring = schaal_a
            engine = None
            members: ClassVar[dict[str, object]] = {}

        context = ChatContext(lobby=FakeLobby(), session=None, catalog=catalog)  # type: ignore[arg-type]

        ruleset_text = "\n".join(handle_chat_command("!ruleset", context))
        assert "Klassiek wiezen" in ruleset_text
        assert "pakjes" in ruleset_text  # Dutch aliases, not English field names

        counting_text = "\n".join(handle_chat_command("!counting", context))
        assert "Schaal A" in counting_text
        assert "tegenstander" in counting_text
        assert "solo_slim" in counting_text

        score_text = "\n".join(handle_chat_command("!score", context))
        assert "nog geen" in score_text  # no game running yet

    def test_every_command_has_a_help_text_that_exists(self, catalog: TextCatalog) -> None:
        for name, (_handler, help_key) in COMMANDS.items():
            assert help_key in catalog, f"!{name} verwijst naar ontbrekende tekst {help_key}"


class TestTextCatalog:
    def test_missing_keys_fail_loudly(self, catalog: TextCatalog) -> None:
        with pytest.raises(MissingTextError):
            catalog.render("dit.bestaat.niet")

    def test_missing_placeholders_fail_loudly(self, catalog: TextCatalog) -> None:
        with pytest.raises(MissingTextError):
            catalog.render("lobby.welcome")  # needs {speler}

    def test_every_key_used_in_the_code_exists(self, catalog: TextCatalog) -> None:
        # Guards the one thing that would otherwise only break at runtime, in
        # front of players: a text key that was renamed in only one place.
        pattern = re.compile(r"""(?:render|catalog\.render)\(\s*["']([a-z0-9_.]+)["']""")
        used: set[str] = set()
        for path in SERVER_SRC.rglob("*.py"):
            used |= set(pattern.findall(path.read_text(encoding="utf-8")))
        # Contract names are built dynamically as contract.name.<key>.
        missing = {key for key in used if key not in catalog}
        assert not missing, f"ontbrekende tekstsleutels: {sorted(missing)}"

    def test_contract_names_are_all_present(self, catalog: TextCatalog) -> None:
        from jwies_core.contracts import CONTRACT_CATALOG

        for key in CONTRACT_CATALOG:
            assert f"contract.name.{key.value}" in catalog

    def test_every_suit_has_both_casings(self, catalog: TextCatalog) -> None:
        from jwies_core.cards import Suit

        for suit in Suit:
            assert f"suit.{suit.value}" in catalog
            assert f"suit_lower.{suit.value}" in catalog

    def test_every_error_code_has_a_text(self, catalog: TextCatalog) -> None:
        from jwies_protocol import ErrorCode

        for code in ErrorCode:
            assert f"error.{code.value}" in catalog, f"geen tekst voor foutcode {code.value}"
