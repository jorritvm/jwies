"""Headless lobby server for Vlaamse wies.

Runs indefinitely, hosts many games at once, and speaks JSON over websockets so
a browser client and a PyQt client can sit at the same table.
"""

__version__ = "0.2.0"

__all__ = ["__version__"]
