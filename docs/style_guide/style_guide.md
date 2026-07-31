# Style Guide

## General

Stick to PEP8 style guide as much as possible. `ruff` enforces the mechanical
part of this; run `uv run ruff check .` before committing.

## Language: English code, Dutch to the player

This is the rule that shapes the most decisions in the codebase.

- **Identifiers, comments, docstrings, log messages, commit messages: English.**
- **Anything a player reads: Dutch.** UI labels, chat, error messages,
  documentation aimed at whoever hosts a game, and the settings files.

Concretely:

- Server-side Dutch lives in `presenter.py` and `chat.py`, as literals at the
  place that sends them, plus the handful of error sentences at their raise
  sites. There is no text catalog: jwies is Vlaamse wies, there is no second
  language planned, and a key indirection costs a file lookup every time you
  want to know what a line says. If a second language ever becomes real, those
  two modules are the extraction points.
- Each client owns Dutch **only** for its own widgets:
  `jwies_web_client/static/js/labels.js` and the label tables in
  `jwies_qt_client/main_window.py`. Game sentences
  (bid announcements, contract statements, the settlement) arrive from the
  server ready to display, so they are written once.
- Wire message types and event names stay English (`play_card`,
  `trick_completed`): they are internal identifiers, not player-facing text.

## Settings models

Settings files are edited by hand by whoever hosts a game, so their keys are
Dutch. The models keep English field names and supply Dutch aliases:

```python
dealer_may_shuffle: Annotated[
    bool,
    Field(alias="deler_mag_schudden", description="Mag de deler schudden?"),
] = False
```

- Inherit from `DutchModel`, which sets `populate_by_name`, `frozen`, and
  `extra="forbid"`. Forbidding extras turns a host's typo into a startup error
  instead of a silently ignored rule.
- The `description` mirrors the comment above that key in the templates.
- **Every key in a template must be preceded by a comment** explaining what it
  does, and for enumerated settings, which values are allowed. This is enforced
  by `tests/config/test_templates.py`, not left to discipline.

## Async

- `jwies-core` is synchronous and stays that way. No `async def`, no `asyncio`
  import, no timers. `tests/core/test_purity.py` enforces it.
- Everything async lives in `jwies-server`. All mutation of a `GameEngine`
  happens inside that lobby's single task, so no locks are needed anywhere.

## JavaScript

The web client has no build step and no framework, deliberately: it is served
straight from the Python package.

- ES modules, no bundler, no npm, no transpilation.
- 2-space indent, semicolons, double quotes.
- `const` by default, `let` when reassigning, never `var`.
- Never insert untrusted text with `innerHTML`; use `textContent` or the
  `escapeHtml` helper in `table.js`.

## Capitalization

PyQt are automatically generated python bindings for the C++ Qt framework.  
In the C++ API camelCase is used.  
As a consequence, PyQt has camelCase bindings...

Any code added to this repository should follow the python PEP8 style guide.  
Some examples:

- classes should be named using CamelCase
- functions and variables should be named using snake_case
- constants should be named using ALL_CAPS_WITH_UNDERSCORES
- use 4 spaces for indentation
- use spaces around operators and after commas

There is one exception to this rule:

- When overriding or interacting with Qt API methods, one must follow camelCase.

When using Qt Designer to create UI files, the generated Python code will use camelCase by default for the widgets.   
For all widgets the application interacts with (e.g. buttons, labels, etc.), the developer must modify this to use
snake_case names.

## Avoid the use of abbreviations in names as much as possible

While the abbreviation may seem clear at the time of writing, it may not be clear to others later on.  
E.g. ´fi´ could be interpreted as 'file', 'file_info', etc.

| Approved abbreviations | Discouraged abbreviations |
|------------------------|---------------------------|
| app, i, j              | fi, pos, dir, d, f        |

i, j are allowed as loop variables in for loops, but should not be used in other contexts.

## Files en folder variable names

Avoid using `dir, d, fi, f`  
Instead use:

- `file` for files (objects)
- `file_name` for base file names (str)
- `file_path` for full file paths, absolute or relative (str)


- `folder` for folders (objects)
- `folder_name` for base folder names (str)
- `folder_path` for full folder paths, absolute or relative (str)

Use prefixes to make it more specific if required. E.g.:

- `image_file` for image files