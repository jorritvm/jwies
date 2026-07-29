"""Client-side settings, stored as YAML next to the old player.ini.

Only remembers how to reach the server and who you are; every game rule now
lives on the server, so the old settings dialog is gone entirely.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

__all__ = ["ClientSettings", "default_settings_path"]

DEFAULT_URL = "ws://127.0.0.1:8000/ws"


def default_settings_path() -> Path:
    return Path.home() / ".jwies" / "player.yaml"


@dataclass
class ClientSettings:
    server_url: str = DEFAULT_URL
    username: str = ""
    resume_token: str | None = None
    last_lobby: str | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> ClientSettings:
        path = path or default_settings_path()
        if not path.is_file():
            return cls()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return cls()
        known = {field: data[field] for field in cls().__dict__ if field in data}
        return cls(**known)

    def save(self, path: Path | None = None) -> None:
        path = path or default_settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(asdict(self), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except OSError:
            # Not being able to remember the session is inconvenient, not fatal.
            pass
