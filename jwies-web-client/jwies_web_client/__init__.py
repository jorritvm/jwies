"""The browser client for Vlaamse wies, with its own little webserver.

The static files live under ``static/``; ``server.py`` hands them out. That
server is deliberately separate from ``jwies-server`` and keeps serving the
page while the game server is down or restarting.

The client is *thin*, like the PyQt one: which cards may be played, who may
bid what, and who won a trick all arrive from the game server, which ships
the permitted options with every prompt. ``tests/e2e/test_web_client.py``
asserts that this stays true.
"""

from pathlib import Path

__version__ = "0.2.0"

__all__ = ["STATIC", "__version__"]

# The web root: index.html, css/, js/ and assets/svg-cards.svg. The card sheet
# is a plain copy of the Qt client's, so neither needs a package to share it.
STATIC = Path(__file__).parent / "static"
