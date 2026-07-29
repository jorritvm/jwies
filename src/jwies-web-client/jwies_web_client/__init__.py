"""The browser client for Vlaamse wies.

This package contains no Python logic - only static HTML, CSS and JavaScript
under ``static/``, plus the accessor below so a server can find and serve them.
The browser is the runtime; there is no build step, no npm and no bundler.

It is a *thin* client, like the PyQt one: it holds no rules. It never decides
which cards may be played, who may bid what, or who won a trick. All of that
arrives from the server, which ships the permitted options with every prompt.
``tests/e2e/test_web_client.py`` asserts that this stays true.
"""

from importlib.resources import files
from importlib.resources.abc import Traversable

__all__ = ["ENTRY_POINT", "static_root"]

ENTRY_POINT = "index.html"


def static_root() -> Traversable:
    """The directory to serve as the web root."""
    return files(__name__) / "static"
