"""PyQt6 client for Vlaamse wies.

A renderer, not a player: it draws whatever the server sends and enables the
options the server offers. It carries no rules, no bidding ladder and no
scoring - which is why it can never disagree with the server about them.

The card sheet and the icons sit in ``assets/`` next to this file. They are
deliberately a copy of the ones the web client serves: two small files beat a
package that exists only to hand out two small files.
"""

from pathlib import Path

__version__ = "0.2.0"

__all__ = ["ASSETS", "__version__"]

ASSETS = Path(__file__).parent / "assets"
