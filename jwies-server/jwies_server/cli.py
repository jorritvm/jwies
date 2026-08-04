"""Command-line entry point.

    jwies-server --config config/server.yaml

Headless: logs to a file or stdout, configured via YAML.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from jwies_core.config.loader import ConfigError
from jwies_server import __version__

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jwies-server",
        description="Headless server voor Vlaamse wies.",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="pad naar het YAML-bestand met serverinstellingen",
    )
    parser.add_argument("--host", default=None, help="overschrijft het adres uit de config")
    parser.add_argument(
        "--port", default=None, type=int, help="overschrijft de poort uit de config"
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="overschrijft het logniveau uit de config",
    )
    parser.add_argument(
        "--log-file", default=None, help="overschrijft het logbestand uit de config"
    )
    parser.add_argument("--version", action="version", version=f"jwies-server {__version__}")
    return parser


def configure_logging(level: str, log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Imported late so --help and --version work without the whole web stack.
    import uvicorn

    from jwies_server.app import create_app
    from jwies_server.config import load_server_config

    try:
        loaded = load_server_config(args.config)
    except ConfigError as error:
        print(str(error), file=sys.stderr)
        return 2

    settings = loaded.config
    configure_logging(
        args.log_level or settings.log.level,
        args.log_file if args.log_file is not None else (settings.log.file or None),
    )

    host = args.host or settings.network.host
    port = args.port or settings.network.port

    log = logging.getLogger("jwies_server")
    log.info("jwies-server %s start op http://%s:%s", __version__, host, port)
    log.info("regelsets: %s", ", ".join(sorted(loaded.rulesets)))
    log.info("puntenschalen: %s", ", ".join(sorted(loaded.scorings)))

    uvicorn.run(create_app(loaded), host=host, port=port, log_config=None)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
