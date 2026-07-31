"""The browser client for Vlaamse wies, with its own little webserver.

The static files live under ``static/``; ``server.py`` hands them out. That
server is deliberately separate from ``jwies-server``: it holds no state, knows
nothing about the rules, and keeps serving the page while the game server is
down or restarting.

The client is *thin*, like the PyQt one: it holds no rules. It never decides
which cards may be played, who may bid what, or who won a trick. All of that
arrives from the game server, which ships the permitted options with every
prompt. ``tests/e2e/test_web_client.py`` asserts that this stays true.
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

__version__ = "0.2.0"

__all__ = ["ENTRY_POINT", "__version__", "static_root"]

ENTRY_POINT = "index.html"


def static_root() -> Traversable:
    """The directory to serve as the web root."""
    return files(__name__) / "static"
