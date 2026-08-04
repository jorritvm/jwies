"""Command-line entry point for the PyQt client.

    jwies --username Jan --server ws://mijnserver:8000/ws

The ``--username`` flag launches under a name different from the one saved in
settings, without editing the settings file.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from jwies_qt_client import __version__

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jwies", description="PyQt6-client voor Vlaamse wies.")
    parser.add_argument("--username", default=None, help="jouw spelersnaam")
    parser.add_argument("--server", default=None, help="websocket-adres van de server")
    parser.add_argument("--settings", default=None, type=Path, help="pad naar player.yaml")
    parser.add_argument(
        "--no-autoconnect",
        action="store_true",
        help="toon het verbindingsvenster in plaats van meteen te verbinden",
    )
    parser.add_argument("--version", action="version", version=f"jwies {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from PyQt6.QtWidgets import QApplication

    from jwies_qt_client.main_window import MainWindow
    from jwies_qt_client.settings import ClientSettings

    settings = ClientSettings.load(args.settings)
    if args.username:
        # A different name means a different player, so the old resume token
        # must not travel with it.
        if args.username != settings.username:
            settings.resume_token = None
        settings.username = args.username
    if args.server:
        settings.server_url = args.server

    application = QApplication(sys.argv[:1])
    window = MainWindow(settings)
    window.show()

    if args.no_autoconnect or not settings.username:
        window.ask_to_connect()
    else:
        window.autoconnect()

    return application.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
