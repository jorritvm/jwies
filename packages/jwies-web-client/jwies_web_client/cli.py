"""Command-line entry point for the web client server.

    jwies-web --port 8080 --game-server ws://mijnserver:8000/ws

Runs independently of the game server. Handy on a homeserver: the page keeps
loading even while ``jwies-server`` is restarting or broken.
"""

from __future__ import annotations

import argparse
import logging
import sys

from jwies_web_client import __version__

__all__ = ["build_parser", "main"]

DEFAULT_PORT = 8080


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jwies-web",
        description="Serveert de browserclient voor Vlaamse wies.",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="adres om op te luisteren (standaard 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"poort (standaard {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--game-server",
        default=None,
        metavar="URL",
        help=(
            "websocket-adres van de spelserver, bijvoorbeeld "
            "ws://127.0.0.1:8000/ws. Laat weg wanneer de spelserver op hetzelfde "
            "adres bereikbaar is; spelers kunnen het ook zelf invullen."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logniveau",
    )
    parser.add_argument("--version", action="version", version=f"jwies-web {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    import uvicorn

    from jwies_web_client.server import create_app

    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    log = logging.getLogger("jwies_web_client")
    log.info("jwies-web %s start op http://%s:%s", __version__, args.host, args.port)
    if args.game_server:
        log.info("spelserver: %s", args.game_server)
    else:
        log.info(
            "geen --game-server opgegeven; de browser probeert hetzelfde adres "
            "en spelers kunnen zelf een adres invullen"
        )

    uvicorn.run(
        create_app(args.game_server), host=args.host, port=args.port, log_config=None
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
