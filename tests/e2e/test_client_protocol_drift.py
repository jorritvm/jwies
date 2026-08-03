"""Neither client may fall behind the server's message shapes.

Both clients speak the wire with string literals: they hand-build the JSON they
send and read raw dicts back. That is deliberate - it is what keeps the browser
client buildless and the PyQt client free of any dependency on the server - but
it means a renamed field on the server breaks them *silently*. Nothing else in
the suite would notice: ``tests/qt/test_qt_window.py`` drives the real window
from a hand-written fixture, so it would stay green against a stale shape while
both clients rendered blanks.

This test closes that gap. It reads the two clients as text, pulls out every
message type and wire field name they mention, and asserts each one still exists
in the protocol models.

It is deliberately one-directional. A field the server has and no client reads is
fine and common; a name a client uses that the server does not have is a bug.

**What it cannot catch**, so that nobody trusts it further than it goes:

- a rename to another name that also exists (``winner_seat`` -> ``seat``)
- a change of meaning or type (``totals`` from a mapping to a list)
- computed keys (``message[key]``), JS destructuring, or a receiver named
  something outside ``WIRE_RECEIVERS``
- anything in the browser's ``index.html``

The Python side is parsed with ``ast`` - it is Python, so a real parse costs the
same as a regex and cannot be fooled by a string. The JavaScript is matched with
regexes, following ``test_the_javascript_and_python_agree_on_card_ids``: there is
no JS parser available here, and ``test_the_web_client_has_no_build_step`` is
what stops one being added.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import get_args

from jwies_server.protocol import (
    ClientEnvelope,
    ClientMessage,
    ProtocolModel,
    ServerEnvelope,
    ServerMessage,
)

ROOT = Path(__file__).resolve().parents[2]
QT = ROOT / "packages" / "jwies-qt-client" / "jwies_qt_client"
JS = ROOT / "packages" / "jwies-web-client" / "jwies_web_client" / "static" / "js"

# Identifiers that hold a raw wire object. A field read off one of these is a
# wire name; a field read off anything else is not.
#
# Whitelisting the *receiver* rather than the file is what makes this workable:
# both clients copy top-level snapshot fields into their own vocabulary but pass
# nested structures through verbatim, so wire names surface in table_scene.py
# and table.js as much as in the two reducers.
#
# `state` and `self` are pointedly absent: those are each client's own store,
# where `show_last_trick`, `in_game` and `openHands` live. Reading them as wire
# names would be pure noise.
WIRE_RECEIVERS = frozenset(
    {"message", "snapshot", "lobby", "seat", "contract", "prompt", "bid", "entry", "envelope"}
)

# `option` is not in that set on purpose: in main.js it holds a bid option in one
# function and a DOM <option> element in another, so the two cannot be told
# apart. Nothing is lost - the same fields are reached through `bid` elsewhere.

# Names a client reads off a wire object that are genuinely not wire fields.
# Every entry needs a comment saying why. If this grows, the whitelist above is
# wrong and should be narrowed instead.
NOT_WIRE_NAMES: frozenset[str] = frozenset()


# --- what the protocol actually defines --------------------------------------


def _members(union: object) -> list[type[ProtocolModel]]:
    """The concrete models inside an ``Annotated[A | B | ..., Field(...)]`` alias."""
    return list(get_args(get_args(union)[0]))


def _message_types(union: object) -> set[str]:
    return {str(model.model_fields["type"].default) for model in _members(union)}


def _nested_models(annotation: object) -> list[type[ProtocolModel]]:
    """Every ProtocolModel reachable from one field annotation."""
    found: list[type[ProtocolModel]] = []
    stack = [annotation]
    while stack:
        current = stack.pop()
        if isinstance(current, type) and issubclass(current, ProtocolModel):
            found.append(current)
        stack.extend(get_args(current))
    return found


def _every_field_name() -> set[str]:
    """Every field name on every model reachable from the two unions.

    Checked as one flat set rather than per message: a variable called `message`
    in store.js holds any of a dozen types, and working out which would need real
    dataflow analysis. The flat check still catches the failure that matters - a
    name that exists nowhere at all.
    """
    names: set[str] = set()
    seen: set[type[ProtocolModel]] = set()

    def walk(model: type[ProtocolModel]) -> None:
        if model in seen:
            return
        seen.add(model)
        for name, field in model.model_fields.items():
            names.add(name)
            for nested in _nested_models(field.annotation):
                walk(nested)

    for model in (*_members(ClientMessage), *_members(ServerMessage)):
        walk(model)
    walk(ClientEnvelope)
    walk(ServerEnvelope)
    return names


# --- reading the PyQt client --------------------------------------------------


def _qt_trees() -> list[ast.Module]:
    return [ast.parse(path.read_text(encoding="utf-8")) for path in sorted(QT.rglob("*.py"))]


def _string_constants(node: ast.expr) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Tuple | ast.List | ast.Set):
        return {name for element in node.elts for name in _string_constants(element)}
    return set()


def _qt_sent() -> set[str]:
    """Message types passed to ``connection.send("...")``."""
    found: set[str] = set()
    for tree in _qt_trees():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "send"
                and node.args
            ):
                found |= _string_constants(node.args[0])
    return found


def _wire_keys(root: ast.AST) -> set[str]:
    """Keys read off a wire object: ``message["x"]`` and ``message.get("x")``."""
    found: set[str] = set()
    for node in ast.walk(root):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id in WIRE_RECEIVERS
        ):
            found |= _string_constants(node.slice)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in WIRE_RECEIVERS
            and node.args
        ):
            found |= _string_constants(node.args[0])
    return found


def _qt_fields() -> set[str]:
    return {key for tree in _qt_trees() for key in _wire_keys(tree)}


def _holds_a_message_type(function: ast.AST) -> set[str]:
    """Locals in this function assigned from ``<wire object>["type"]``."""
    holders: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and "type" in _wire_keys(node.value):
                holders.add(target.id)
    return holders


def _qt_received() -> set[str]:
    """Message types compared against the value read from ``message["type"]``.

    Scoped per function rather than by variable name, because the client also
    uses a local called ``kind`` for the *prompt* kind - ``shuffle``, ``cut``,
    ``bid``, ``play`` - which is an entirely different vocabulary that happens to
    live behind the same word.
    """
    found: set[str] = set()
    for tree in _qt_trees():
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            holders = _holds_a_message_type(function)
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Compare)
                    and isinstance(node.left, ast.Name)
                    and node.left.id in holders
                ):
                    for comparator in node.comparators:
                        found |= _string_constants(comparator)
    return found


# --- reading the browser client -----------------------------------------------

_JS_SENT = re.compile(r'\.send\(\s*"([a-z_]+)"')
_JS_CASE = re.compile(r'case\s+"([a-z_]+)"\s*:')
_JS_MESSAGE_TYPE_EQUALS = re.compile(r'\bmessage\.type\s*===\s*"([a-z_]+)"')
# `\??` catches optional chaining, as in `state.prompt?.kind`.
_JS_FIELD = re.compile(
    r"\b(?:" + "|".join(sorted(WIRE_RECEIVERS)) + r")\??\.([a-z][A-Za-z0-9_]*)\b"
)


def _js_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(JS.glob("*.js")))


def _js_switch_bodies(source: str, discriminant: str) -> list[str]:
    """The brace-balanced body of every ``switch (<discriminant>)``.

    Worth the ten lines: an unscoped ``case "..."`` sweep also picks up the
    switches over bid types, and a drift test that cries wolf is a drift test
    somebody deletes.
    """
    bodies: list[str] = []
    opening = re.compile(r"switch\s*\(\s*" + re.escape(discriminant) + r"\s*\)\s*\{")
    for match in opening.finditer(source):
        depth, index = 1, match.end()
        while index < len(source) and depth:
            depth += {"{": 1, "}": -1}.get(source[index], 0)
            index += 1
        bodies.append(source[match.end() : index])
    return bodies


def _js_received(source: str) -> set[str]:
    found = set(_JS_MESSAGE_TYPE_EQUALS.findall(source))
    for body in _js_switch_bodies(source, "message.type"):
        found |= set(_JS_CASE.findall(body))
    return found


# --- the assertions -----------------------------------------------------------


def test_every_message_the_qt_client_sends_exists() -> None:
    unknown = _qt_sent() - _message_types(ClientMessage)
    assert not unknown, f"qt-client stuurt onbekende berichttypes: {sorted(unknown)}"


def test_every_message_the_browser_sends_exists() -> None:
    unknown = set(_JS_SENT.findall(_js_source())) - _message_types(ClientMessage)
    assert not unknown, f"webclient stuurt onbekende berichttypes: {sorted(unknown)}"


def test_every_message_the_qt_client_handles_exists() -> None:
    unknown = _qt_received() - _message_types(ServerMessage)
    assert not unknown, f"qt-client verwacht onbekende berichttypes: {sorted(unknown)}"


def test_every_message_the_browser_handles_exists() -> None:
    unknown = _js_received(_js_source()) - _message_types(ServerMessage)
    assert not unknown, f"webclient verwacht onbekende berichttypes: {sorted(unknown)}"


def test_every_field_the_qt_client_reads_exists() -> None:
    unknown = _qt_fields() - _every_field_name() - NOT_WIRE_NAMES
    assert not unknown, f"qt-client leest onbekende velden: {sorted(unknown)}"


def test_every_field_the_browser_reads_exists() -> None:
    unknown = set(_JS_FIELD.findall(_js_source())) - _every_field_name() - NOT_WIRE_NAMES
    assert not unknown, f"webclient leest onbekende velden: {sorted(unknown)}"


# --- guards on the extraction itself ------------------------------------------


def test_the_extraction_still_finds_things() -> None:
    """A regex or a walk that quietly stops matching would pass every test above.

    These floors are what make the rest of this file worth having: they fail
    loudly if a client is restructured in a way this test can no longer read,
    instead of silently going vacuous.
    """
    source = _js_source()
    qt_fields, js_fields = _qt_fields(), set(_JS_FIELD.findall(source))

    assert len(_qt_sent()) >= 10, "te weinig verstuurde berichten gevonden in de qt-client"
    assert len(set(_JS_SENT.findall(source))) >= 8, "te weinig gevonden in de webclient"
    assert len(_qt_received()) >= 6, "de berichtafhandeling van de qt-client is niet gevonden"
    assert len(_js_received(source)) >= 6, "de berichtafhandeling van de webclient idem"
    assert len(qt_fields) >= 20 and len(js_fields) >= 15

    # Spot checks on names that only disappear if something is badly wrong.
    assert {"your_hand", "legal_cards"} <= qt_fields
    assert {"your_hand", "legal_cards"} <= js_fields


def test_the_escape_hatch_stays_small() -> None:
    assert len(NOT_WIRE_NAMES) < 10, "WIRE_RECEIVERS is te breed geworden"
