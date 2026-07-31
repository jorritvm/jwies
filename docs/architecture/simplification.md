# Simplification analysis

> **Status: executed 2026-07-31.** All eight items below have landed on
> `huge_refactor`. What actually changed, and where the analysis was wrong:
>
> | | outcome |
> |---|---|
> | **A** protocol package | `jwies_protocol` → `jwies_server.protocol`. Four packages now. The Qt client hardcodes `PROTOCOL_VERSION` and a test asserts it imports nothing from `jwies_server` or `jwies_core`. The `*Code` enums are now aliases (`SuitCode = Suit`), so the six parity tests are gone. `ClientKind` became a bounded string. |
> | **B** snapshot-only state | Done, and further than proposed: `round_started`, `hand_dealt`, `trump_turned`, `trump_hidden`, `bid_placed`, `redeal`, `contract_established` and `prompt` are deleted outright. The clients fold in `snapshot` plus exactly three trick messages. `store.js` 197→149, `state.py` 143→124. |
> | **C** dead code | All removed except `card_label()`, which the analysis got wrong: `table_scene.py:83` uses it for tooltips. |
> | **D** duplicated tables | Half done via (A). The card→SVG tables stay duplicated across the JS↔Python boundary, with the parity test, as the doc recommends. |
> | **E** dispatch layers | `_to_action` gone; each action message is a `GameAction` with `to_action()`. Two of the four `match` statements remain, both load-bearing. |
> | **F** LobbyRuntime | 661→~535. `build_snapshot()` lives in `jwies_server/snapshot.py` as a pure function of `(lobby, occupants, engine, presenter, seat, paused, missing)`. The presenter is cached and invalidated on membership change. |
> | **G** text catalog | **Decided: inlined.** `texts.py`, `texts/nl.yaml` and the key-parity tests are gone; every sentence reads at its call site. Two lookup tables survive (`CONTRACT_NAMES`, `SUIT_NAMES`) with coverage tests. |
> | **H** modals in render | `refresh_prompt` is pure. `react_to_prompt` runs only from `on_message`, remembers the prompt it acted on, and is covered by six tests. `ConnectDialog` and the lobby page moved to `lobby_page.py` (`main_window.py` 427→372). |
>
> The line count did **not** land at 6 000: application Python is ~6 900,
> because the deleted code was largely replaced by comments explaining the
> invariants that replaced it. That trade was deliberate. The goal the doc
> actually names - "how does a played card become pixels" - did land: one
> message type, one reducer arm, one snapshot.
>
> The original analysis follows unchanged, as the record of why.

---

Written 2026-07-31, against `huge_refactor` at the point where `jwies-assets`
was folded into the two clients.

The trigger was "we went from 3k lines to 10k". That is true as a count, but
the count is not where the pain is. This document separates the two: first an
honest ledger of where the lines actually went, then the things that genuinely
raise the cost of understanding this code, ranked by how much they buy back.

---

## 1. Where the 10k actually is

| | lines |
|---|---:|
| `jwies-core` | 2 456 |
| `jwies-server` | 2 218 |
| `jwies-qt-client` | 1 366 |
| `jwies-protocol` | 812 |
| `jwies-web-client` (Python) | 171 |
| **application Python** | **7 023** |
| browser client (JS + CSS + HTML) | 1 567 |
| tests | 2 809 |

The old tree was 3 746 lines under `src/`, but 1 008 of those were generated
`.ui` XML and its generated Python. Hand-written old code: **≈2 738 lines**,
with no tests, one client, no server-side lobbies, no reconnect, no wire
protocol, no configurable rules.

So the fair comparison is 2 738 → 7 023 application lines, and the extra 4 300
bought: a headless server, lobbies and sessions, reconnect/resume, YAML-driven
rulesets and scoring scales, a validated wire protocol, a second (browser)
client, and a text catalog. Plus 2 809 lines of tests that did not exist.

**That is not the problem.** 2.5× the code for that much more product is a
normal price. The problem is that reading any one path through it now crosses
five packages, three dispatch tables and two parallel state models — and a
meaningful fraction of what you cross is dead or duplicated.

Below, in order of leverage.

---

## 2. Ranked findings

### A. `jwies-protocol` does not do the job it exists to do — and one of its two consumers uses one integer from it

The package docstring says:

> The server and the PyQt client both depend on this package so the two Python
> sides cannot drift.

They do not. The entire Qt client's use of `jwies-protocol` is:

```
packages/jwies-qt-client/jwies_qt_client/net.py:16:  from jwies_protocol import PROTOCOL_VERSION
```

That is the whole list. The Qt client never constructs a protocol model and
never validates one. It hand-builds dicts on the way out
(`connection.send("play_card", card=code)`, `net.py:118`) and reads raw dicts on
the way in (`state.py:apply_message`, which switches on `message.get("type")`
string literals). It is, structurally, exactly as loosely coupled as the browser
client — which depends on nothing at all.

So the 812-line package, a workspace member with its own `pyproject.toml`,
version, ruff exemption and bumpversion entry, is a server-internal schema plus
one `int` exported to a client.

**Do:** move `jwies_protocol` into `jwies_server` as `jwies_server.protocol`.
Have the Qt client hardcode `PROTOCOL_VERSION = 1` next to the rest of its wire
constants (it already hardcodes every message type name and every field name).

**Buys:** one fewer package, one fewer pyproject, one fewer version to bump, and
— more importantly — it stops implying a type-safety guarantee that does not
exist. If you *want* that guarantee, the fix is the opposite: make the Qt client
actually parse `ServerEnvelope` and construct `ClientMessage`. Pick one. Right
now you pay for the second and get the first.

Related: `ClientKind` (`common.py:99`) is validated on the way in and never read
by anything. `test_protocol.py:133` asserts its members exist. That is a test of
a field nobody consumes.

---

### B. The snapshot and the event stream are two complete, independently maintained render paths

`snapshot.py:1` states the intended design:

> Both clients must be able to draw a full table from a snapshot alone; the
> incremental events exist only for animation and chat flavour.

But that is not how the clients are built. Both implement a **full ~25-case
event reducer** *in addition to* the snapshot applier:

- `packages/jwies-qt-client/jwies_qt_client/state.py:78-143` — `apply_message`
- `packages/jwies-web-client/.../js/store.js:79-180` — `applyMessage`

These two are the same switch statement written twice in two languages. Every
new server message means editing both. Every field rename means editing both.
And each is a second, hand-rolled derivation of state that the snapshot already
computes correctly on the server.

The server side mirrors it: `Presenter.messages_for` (`presenter.py:162-272`) is
110 lines whose only job is turning each engine event into the wire messages
those two reducers consume.

**Do:** make the snapshot the only state path. After any action that changes the
table, `_dispatch` sends each seat a fresh `Snapshot`. Keep events, but strip
them to what a snapshot genuinely cannot express — "this card moved", "this
trick was swept", and chat lines. A snapshot for one table is ~2 KB and there
are at most four recipients; there is no bandwidth argument here.

**Buys:** `state.py` drops from 143 lines to ~40. `store.js` drops from 197 to
~50. `messages_for` loses most of its cases. And the class of bug where the two
clients disagree about what `trick_completed` does to `last_trick` stops being
possible.

This is the single highest-leverage change in this document.

---

### C. Dead code, in nine places

None of this is called by anything:

| What | Where |
|---|---|
| `PhaseChanged`, `TrumpDecided` messages | `server_messages.py` — never constructed |
| `PromptCleared` message | never constructed, but **both clients handle it** (`state.py:136`, `store.js:158`) |
| `load_agent_factories()`, `AgentFactory`, `AGENT_ENTRY_POINT_GROUP` | `agents.py:42-62` — never called |
| `allowed_agents` config field | `config.py:86` — never read |
| `fill_with_agent` protocol field | `client_messages.py:86` — never read |
| `PlayerAgent.is_human` | `agents.py:31` — declared, set once, never read |
| `_Inbound.agent` | `lobby.py:85` — written at `:203`, never read |
| `Presenter.system()`, `Presenter.cards()` | `presenter.py:312,318` — never called |
| `card_label()` | `cards.py:59` — called only by its own test |

The agent seam deserves a note. `agents.py` is 62 lines documenting "the whole
AI seam", and `PlayerAgent` is a `Protocol` with exactly one implementation
(`WebsocketAgent`) and one consumer (`lobby._send`, which just calls
`.deliver()`). The seam costs a protocol declaration, an entry-point loader, a
config field and a wire field, and today it is load-bearing for nothing. Keep
`PlayerAgent` — it is three lines of real value and it *does* describe how
`_send` works. Delete the loader, the entry-point group, and the two unread
config/wire fields; they can come back in an afternoon when an AI actually
exists.

**Buys:** ~250 lines, and nine fewer things a reader has to decide are
irrelevant.

---

### D. The same card→SVG-id table exists three times, policed by two tests

1. `packages/jwies-core/jwies_core/cards.py` — `Card.svg_element_id`
2. `packages/jwies-qt-client/jwies_qt_client/cards.py:26-40` — `_SUIT_SVG` / `_RANK_SVG`
3. `packages/jwies-web-client/.../js/cards.js` — `SUIT_SVG` / `RANK_SVG`

Kept in sync by `test_every_card_id_the_client_builds_exists_in_the_sheet` and
`test_the_javascript_and_python_agree_on_card_ids` — the second of which parses
the JS source with regexes to compare tables.

The same shape recurs with the enums: `jwies_protocol.common` deliberately
duplicates `SuitCode`, `BidTypeCode`, `ContractKeyCode` and `PhaseCode` from
`jwies_core`, with `test_protocol.py` asserting parity. And again with labels:
`main_window.BID_LABELS` / `STATUS_LABELS` vs `labels.js LABELS.bid` /
`LABELS.status`.

Duplication across a language boundary (JS↔Python) is unavoidable and the test
is the right answer. Duplication *within* Python is not. After (A), the protocol
enums and the core enums are in the same distribution and the parity test can be
replaced by `SuitCode = Suit`.

The `SUIT_SVG` table can also just be sent: the server already renders every
player-visible sentence: it could equally put the element id in the wire card
code, or the clients could derive it from a single mapping served as JSON. That
is a bigger change; the enum de-duplication is the cheap half.

---

### E. Five dispatch points and three `match` statements between a click and the engine

Trace a card being played:

```
browser click
  → net.js send()
  → websocket
  → handle_connection() read loop            connection.py:118
  → _parse()                                 connection.py:147
  → _route()          match #1               connection.py:263
  → lobby.submit() → asyncio.Queue
  → LobbyRuntime._run()                      lobby.py:210
  → _handle()         match #2               lobby.py:387
  → _handle_game_action()  (4 guard clauses) lobby.py:477
  → _to_action()      match #3               lobby.py:517
  → engine.apply()    match #4               engine.py:276
  → _apply_play()                            engine.py:414
```

Four `match` statements on what is essentially the same message identity.

`_route`'s split (lobby-level messages handled inline, game messages forwarded)
is justified — the queue is what makes the engine lock-free, and that is worth
keeping. `_handle`'s re-match is not: it re-tests the same discriminator
`_route` already saw, only to route four cases into one function.

`_to_action` is the pure tax of having `jwies_protocol.PlaceBid` and
`jwies_core.events.PlaceBid` be different types that mean the same thing. It
exists to translate `client_messages.PlayCard(card="10S")` into
`events.PlayCard(card=Card.from_code("10S"))`.

**Do:** after (A), let the engine's `Action` types *be* the protocol's action
types, or give each protocol action a `to_action()` method so the translation
lives next to the type it translates. Merge `_handle`'s four game cases into the
default arm.

**Buys:** two of the four matches, and the ability to `Ctrl-click` from a wire
message to the engine method that handles it.

---

### F. `LobbyRuntime` is 661 lines doing five jobs

`lobby.py` currently owns: membership bookkeeping, the asyncio task and inbox,
message routing, snapshot construction, engine driving, and disconnect/reconnect
policy. `snapshot_for()` alone is 82 lines of field-by-field transcription
(`lobby.py:278-360`), and `_seat_infos()` another 17.

Snapshot building is the one piece with no coupling to the rest: it is a pure
function of `(engine, members, status, presenter)`. Moving it to
`snapshot.py` next to `Presenter` would take ~100 lines out of the file and make
both testable without an event loop.

While in there: `LobbyRuntime.presenter` (`lobby.py:135`) is a `@property` that
constructs a new `Presenter` **and** walks every member to rebuild `seat_names()`
on each access — and it is accessed 16 times in this file, several times per
inbound message. Make it a cached attribute invalidated on membership change.

---

### G. The text catalog: 4 layers for a single-language game

Every player-visible sentence goes: `nl.yaml` → `TextCatalog.load()` →
`catalog.render("bid.ask", speler=…, troef=…)` → the string. Supported by a test
asserting every key used exists in the file *and* every key in the file is used.

The value of this is one-language-per-file translation. The game is Flemish
wiezen; there is no second language planned, and the enum values, error
messages, config aliases and chat commands are already Dutch throughout the
codebase. What you pay is: you cannot read a sentence at its call site. To know
what `catalog.render("round.made", slagen=…, nodig=…)` says, you open another
file.

This is a judgment call, not a defect — but it should be a *decision*. If a
second language is a real goal, keep it. If it is not, inlining the strings into
`presenter.py` and `chat.py` deletes `texts.py`, `nl.yaml`, the parity test, and
one indirection from every sentence in the server. Note that this is the one
item here that is meaningfully hard to reverse, so decide before doing.

---

### H. `refresh_prompt` renders *and* opens modal dialogs

`main_window.py:321-367` is called from `refresh_table()`, which is called from
`on_message()` on **every** incoming message while in a game
(`main_window.py:296`). Inside it:

```python
elif kind == "shuffle":
    answer = QMessageBox.question(...)     # blocking modal
    self.connection.send("answer_shuffle", ...)
elif kind == "cut":
    count, accepted = QInputDialog.getInt(...)   # blocking modal
```

The client's `prompt` is only cleared by `prompt_cleared` (never sent — see C),
`round_finished`, `game_paused`, or a replacing snapshot. So after the dealer
answers the shuffle, the shuffle prompt stays in client state; the server's next
prompt goes to the *cutter*, not the dealer. The next broadcast message to reach
the dealer — a chat line, a `lobby_state` — re-enters `refresh_prompt` with the
shuffle prompt still set and opens the dialog again. Because Qt runs a nested
event loop inside a modal, the socket keeps delivering while the first dialog is
open, so these can stack.

There is no test covering this path (`tests/qt/test_qt_window.py` never
exercises `refresh_prompt`), so it may or may not bite in practice — but a
render function that opens blocking modals as a side effect is a hazard
regardless.

**Do:** split "draw the current state" from "react to a new prompt". React only
on the `prompt` message in `on_message`, never in the refresh path. This is also
the fix for (B): once snapshots drive rendering, the render path must be pure.

Separately, `main_window.py` at 430 lines holds the connect dialog, the lobby
page, the table page, the message router and every handler. `ConnectDialog` and
the lobby page are the two easy extractions.

---

### I. The test suite is 40% architecture-policing

`tests/e2e/test_web_client.py` alone contains: a forbidden-word list scanning JS
for rules leakage, a `tomllib` check that each `pyproject.toml` lacks certain
dependencies, an assertion that the web client's Python is exactly
`["__init__.py", "cli.py", "server.py"]`, a check that no bundler config exists,
and the JS↔Python id parity test. `tests/core/test_purity.py` and
`tests/config/test_templates.py` are more of the same.

These are not bad tests — they encode real invariants, and the forbidden-word
list caught something worth catching. But most of them exist *because* something
is duplicated across a boundary. The dependency assertions in particular are
guarding boundaries that (A) would remove entirely. Every one that survives (B),
(C) and (D) is one you should keep; the rest go with the duplication.

---

## 3. Suggested order

Roughly by (value ÷ risk):

1. **(C) Delete the dead code.** Mechanical, zero-risk, ~250 lines, and it
   shrinks the surface every later step has to reason about.
2. **(A) Fold `jwies-protocol` into `jwies-server`.** One package, one
   pyproject, one version, one bumpversion entry, one ruff exemption gone. Kills
   the enum-parity duplication as a side effect.
3. **(H) Get the modals out of the render path.** Small, and it is the
   prerequisite for (B) on the Qt side.
4. **(B) Snapshot as the only state path.** The big one. ~250 client lines and
   the entire two-reducers-must-agree problem.
5. **(F) Extract snapshot building out of `LobbyRuntime`; cache the presenter.**
6. **(E) Collapse `_to_action` and `_handle`'s redundant match.**
7. **(G) Decide on the text catalog** — deliberately, either way.

Steps 1–4 land the codebase around 6 000 application lines with three packages,
and — the actual goal — reduce "how does a played card become pixels" from five
files and four dispatch tables to two files and two.

## 4. What not to touch

For balance, the parts that are carrying their weight and should be left alone:

- **`jwies-core` as a pure, sync, I/O-free package.** This is the best thing in
  the repo. `test_purity.py` is worth keeping forever.
- **The single-inbox-queue lobby.** No locks anywhere, deterministic ordering,
  and pause/resume falls out of `pending()` being idempotent. That is a genuinely
  good design and it is why reconnect is 20 lines instead of 200.
- **`CONTRACT_CATALOG` as data instead of the old 125-line if/elif ladder.**
- **Seeded RNG injection.** Cheap, and it is what makes the e2e tests possible.
- **No build step for the browser client.** Keep it that way.
