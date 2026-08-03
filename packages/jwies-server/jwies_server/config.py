"""Server configuration model."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from jwies_core.config import Ruleset, ScoringScale, load_ruleset, load_scoring_scale
from jwies_core.config.base import SCHEMA_VERSION, DutchModel
from jwies_core.config.loader import ConfigError, parse_model
from pydantic import Field, model_validator

__all__ = ["LobbySettings", "LogSettings", "NetworkSettings", "ServerConfig", "load_server_config"]


class NetworkSettings(DutchModel):
    host: Annotated[
        str,
        Field(alias="adres", description="Op welk adres luistert de server?"),
    ] = "0.0.0.0"
    port: Annotated[
        int,
        Field(ge=1, le=65535, alias="poort", description="Op welke poort luistert de server?"),
    ] = 8000


class LobbySettings(DutchModel):
    maximum: Annotated[
        int,
        Field(
            ge=1,
            alias="maximum_aantal",
            description="Hoeveel lobby's mogen er tegelijk bestaan?",
        ),
    ] = 20
    reap_after_minutes: Annotated[
        int,
        Field(
            ge=1,
            alias="opruimen_na_minuten",
            description="Na hoeveel minuten zonder spelers wordt een lobby opgeruimd?",
        ),
    ] = 60


class LogSettings(DutchModel):
    level: Annotated[
        str,
        Field(alias="niveau", description="Logniveau: DEBUG, INFO, WARNING of ERROR."),
    ] = "INFO"
    file: Annotated[
        str,
        Field(alias="bestand", description="Logbestand; leeg = enkel naar het scherm."),
    ] = ""

    @model_validator(mode="after")
    def _check_level(self) -> Self:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if self.level.upper() not in allowed:
            raise ValueError(f"onbekend logniveau; toegelaten: {', '.join(sorted(allowed))}")
        return self


class ServerConfig(DutchModel):
    schema_version: Annotated[int, Field(alias="schema_versie")] = SCHEMA_VERSION
    network: Annotated[NetworkSettings, Field(alias="netwerk")] = NetworkSettings()
    lobby: Annotated[LobbySettings, Field(alias="lobby")] = LobbySettings()
    ruleset_paths: Annotated[
        dict[str, str],
        Field(alias="regelsets", description="Beschikbare regelsets, per naam."),
    ]
    scoring_paths: Annotated[
        dict[str, str],
        Field(alias="puntenschalen", description="Beschikbare puntenschalen, per naam."),
    ]
    default_ruleset: Annotated[str, Field(alias="standaard_regelset")]
    default_scoring: Annotated[str, Field(alias="standaard_puntenschaal")]
    log: Annotated[LogSettings, Field(alias="logboek")] = LogSettings()

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"schema_versie {self.schema_version} wordt niet ondersteund "
                f"(verwacht: {SCHEMA_VERSION})"
            )
        if self.default_ruleset not in self.ruleset_paths:
            raise ValueError(
                f"standaard_regelset '{self.default_ruleset}' staat niet bij 'regelsets'"
            )
        if self.default_scoring not in self.scoring_paths:
            raise ValueError(
                f"standaard_puntenschaal '{self.default_scoring}' staat niet bij 'puntenschalen'"
            )
        return self


class LoadedConfig:
    """A validated server config with its rulesets and scales already loaded."""

    def __init__(self, config: ServerConfig, base: Path) -> None:
        self.config = config
        self.base = base
        self.rulesets: dict[str, Ruleset] = {
            name: load_ruleset(self._resolve(path)) for name, path in config.ruleset_paths.items()
        }
        self.scorings: dict[str, ScoringScale] = {
            name: load_scoring_scale(self._resolve(path))
            for name, path in config.scoring_paths.items()
        }

    def _resolve(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else (self.base / candidate).resolve()


def load_server_config(path: str | Path) -> LoadedConfig:
    """Load a server config plus everything it references."""
    path = Path(path).resolve()
    import yaml

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"Kan serverinstellingen '{path}' niet lezen: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(
            f"Fout in serverinstellingen '{path}': ongeldige YAML.\n{error}"
        ) from error

    config = parse_model(ServerConfig, raw, what="serverinstellingen", source=str(path))
    return LoadedConfig(config, path.parent)
