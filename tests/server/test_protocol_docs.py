"""``docs/protocol.md`` must describe every message and field that exists.

The document is hand-written, because the useful half of it is prose a generator
could not produce: which messages carry state and which are announcements, why
exactly three of them bridge the trick-on-the-table gap, why the snapshot is
built per recipient. What a generator *would* produce - the field tables - is
the half that silently rots, so that half is checked here instead.

The check runs one way only, and deliberately: it fails when the models have
something the document does not. Nothing stops the document describing something
that no longer exists... except that the same tables then name a field the models
lack, which ``_documented`` compares by set equality. So both directions are in
fact covered, per message.

The failure mode matters as much as the check. A regenerate-and-diff test fails
with "run the script", which teaches everyone to fix it without reading it. This
one fails with "you added ``table_cleared`` and did not document it", which
cannot be satisfied without writing a sentence. That is the same bargain as
``test_every_template_key_is_preceded_by_a_comment``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from jwies_server.protocol import (
    ClientEnvelope,
    ClientMessage,
    ErrorCode,
    ProtocolModel,
    ServerEnvelope,
    ServerMessage,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "protocol.md"

# Two rules make the document machine-readable, and both are worth keeping for
# human readers too: every message and structure gets an `#### `name`` heading,
# and every field is the first cell of a table row, backticked.
_SUBHEADING = re.compile(r"^#### (.+)$", re.MULTILINE)
_ANY_HEADING = re.compile(r"^#+ ", re.MULTILINE)
_IDENTIFIER = re.compile(r"`(\w+)`")
_FIELD_ROW = re.compile(r"^\|\s*`(\w+)`\s*\|", re.MULTILINE)

# Headings that legitimately cover more than one message, because the messages
# are identical in shape and describing them three times would be worse prose.
# A message only belongs here if its fields match the heading's exactly.
SHARED_HEADINGS = {
    "player_joined": ("player_disconnected", "player_reconnected"),
}


def _documented() -> dict[str, list[set[str]]]:
    """Every ``#### `name`` heading in the document, and the fields under it.

    A name can appear twice: ``lobby_list`` is a message type in *both*
    directions - the client asks, the server answers - so each name maps to the
    list of field sets documented under it.
    """
    text = DOC.read_text(encoding="utf-8")
    sections: dict[str, list[set[str]]] = {}
    for heading in _SUBHEADING.finditer(text):
        # A section ends at the next heading of any level, not just the next
        # `####`: otherwise the last one swallows the tables that follow it.
        following = _ANY_HEADING.search(text, heading.end())
        end = following.start() if following else len(text)
        fields = set(_FIELD_ROW.findall(text[heading.end() : end]))
        for name in _IDENTIFIER.findall(heading.group(1)):
            sections.setdefault(name, []).append(fields)
    for name, aliases in SHARED_HEADINGS.items():
        for alias in aliases:
            sections.setdefault(alias, sections.get(name, [set()]))
    return sections


def _members(union: object) -> list[type[ProtocolModel]]:
    return list(get_args(get_args(union)[0]))


def _reachable() -> dict[str, type[ProtocolModel]]:
    """Every model reachable from the two unions, by class name."""
    found: dict[str, type[ProtocolModel]] = {}

    def nested(annotation: object) -> list[type[ProtocolModel]]:
        models: list[type[ProtocolModel]] = []
        stack = [annotation]
        while stack:
            current = stack.pop()
            if isinstance(current, type) and issubclass(current, ProtocolModel):
                models.append(current)
            stack.extend(get_args(current))
        return models

    def walk(model: type[ProtocolModel]) -> None:
        if model.__name__ in found:
            return
        found[model.__name__] = model
        for field in model.model_fields.values():
            for child in nested(field.annotation):
                walk(child)

    for model in (*_members(ClientMessage), *_members(ServerMessage)):
        walk(model)
    return found


def _messages() -> list[tuple[str, type[ProtocolModel]]]:
    """(wire type name, model) for both directions."""
    return [
        (str(model.model_fields["type"].default), model)
        for model in (*_members(ClientMessage), *_members(ServerMessage))
    ]


def _mismatch(label: str, expected: set[str], candidates: list[set[str]] | None) -> str | None:
    """A complaint, or None if one of the documented sets matches exactly."""
    if candidates is None:
        return f"{label}: geen `#### {label}`-kop in protocol.md"
    if any(actual == expected for actual in candidates):
        return None
    closest = max(candidates, key=lambda actual: len(actual & expected))
    return f"{label}: mist {sorted(expected - closest)}, teveel {sorted(closest - expected)}"


# --- the assertions -----------------------------------------------------------


def test_every_message_type_is_documented() -> None:
    undocumented = {name for name, _ in _messages()} - set(_documented())
    assert not undocumented, f"niet beschreven in protocol.md: {sorted(undocumented)}"


def test_every_message_field_is_documented() -> None:
    documented = _documented()
    wrong = [
        complaint
        for wire_type, model in _messages()
        if (
            complaint := _mismatch(
                wire_type, set(model.model_fields) - {"type"}, documented.get(wire_type)
            )
        )
    ]
    assert not wrong, "velden lopen niet gelijk met protocol.md:\n" + "\n".join(wrong)


def test_every_nested_structure_is_documented() -> None:
    documented = _documented()
    messages = {model for _, model in _messages()}
    wrong = [
        complaint
        for name, model in _reachable().items()
        # Messages are covered by the two tests above, under their wire type.
        if model not in messages
        and (complaint := _mismatch(name, set(model.model_fields), documented.get(name)))
    ]
    assert not wrong, "structuren lopen niet gelijk met protocol.md:\n" + "\n".join(wrong)


def test_both_envelopes_are_documented() -> None:
    documented = _documented()
    for envelope in (ClientEnvelope, ServerEnvelope):
        complaint = _mismatch(
            envelope.__name__, set(envelope.model_fields), documented.get(envelope.__name__)
        )
        assert not complaint, complaint


def test_every_error_code_is_documented() -> None:
    text = DOC.read_text(encoding="utf-8")
    listed = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", text, re.MULTILINE))
    missing = {code.value for code in ErrorCode} - listed
    assert not missing, f"foutcodes zonder uitleg in protocol.md: {sorted(missing)}"


def test_the_parser_found_something() -> None:
    """A regex that quietly stops matching would make every test above vacuous."""
    documented = _documented()
    assert len(documented) >= 25, f"maar {len(documented)} koppen gevonden in protocol.md"
    assert documented["snapshot"] == [{"snapshot"}]
    assert "your_hand" in documented["Snapshot"][0]
    # `lobby_list` really is documented twice, once per direction.
    assert sorted(documented["lobby_list"], key=len) == [set(), {"lobbies"}]


def test_the_documented_version_matches_the_code() -> None:
    from jwies_server.protocol import PROTOCOL_VERSION

    text = DOC.read_text(encoding="utf-8")
    assert f"Versie **{PROTOCOL_VERSION}**" in text, "de versie in protocol.md loopt achter"
