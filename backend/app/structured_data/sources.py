# Creado por Aldo Garcia.
"""Configuracion declarativa de fuentes estructuradas.

``config/data_sources/sources.yaml`` define cada fuente: motor, variable de
entorno con el DSN (nunca el DSN), entidades permitidas, columnas permitidas,
filtros organizacionales obligatorios, timeout y maximo de filas.

El archivo **no contiene secretos**: ``secret_ref`` es el nombre de la variable de
entorno. Si la variable no existe, la fuente queda ``PREPARED_NOT_CONNECTED`` y el
sistema lo declara honestamente en lugar de simular una conexion.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.provider import IntegrationStatus
from app.common.errors import ConfigurationError
from app.common.logging import get_logger
from app.config import get_settings
from app.structured_data.schemas import IDENTIFIER_RE

logger = get_logger(__name__)

SUPPORTED_ENGINES = frozenset({"mysql", "mariadb", "postgresql", "sqlserver", "oracle", "sqlite"})


class EntityConfig(BaseModel):
    """Entidad expuesta: se mapea a una tabla o, preferiblemente, a una vista de seguridad."""

    model_config = ConfigDict(extra="forbid")

    name: str
    table: str
    description: str = ""
    allowed_columns: list[str] = Field(default_factory=list)
    #: Filtros que SIEMPRE se anaden a la consulta (alcance organizacional).
    required_filters: dict[str, str] = Field(default_factory=dict)
    max_rows: int = Field(default=200, ge=1, le=10000)

    @field_validator("name", "table")
    @classmethod
    def _check_identifier(cls, value: str) -> str:
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Identificador invalido: {value!r}")
        return value

    @field_validator("allowed_columns")
    @classmethod
    def _check_columns(cls, value: list[str]) -> list[str]:
        for column in value:
            if not IDENTIFIER_RE.match(column):
                raise ValueError(f"Columna invalida: {column!r}")
        return value


class SourceConfig(BaseModel):
    """Definicion de una fuente estructurada."""

    model_config = ConfigDict(extra="forbid")

    name: str
    engine: str
    description: str = ""
    enabled: bool = False
    #: Nombre de la variable de entorno que contiene el DSN read-only.
    secret_ref: str = ""
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    max_rows: int = Field(default=200, ge=1, le=10000)
    #: Roles de Matrix RH autorizados a consultar la fuente.
    allowed_roles: list[str] = Field(default_factory=list)
    entities: list[EntityConfig] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        if not IDENTIFIER_RE.match(value):
            raise ValueError(f"Nombre de fuente invalido: {value!r}")
        return value

    @field_validator("engine")
    @classmethod
    def _check_engine(cls, value: str) -> str:
        if value not in SUPPORTED_ENGINES:
            raise ValueError(f"Motor no soportado: {value}. Soportados: {sorted(SUPPORTED_ENGINES)}")
        return value

    def entity(self, name: str) -> EntityConfig | None:
        return next((e for e in self.entities if e.name == name), None)

    def dsn(self) -> str | None:
        """Lee el DSN de la variable de entorno referenciada. Nunca se persiste."""
        if not self.secret_ref:
            return None
        return os.environ.get(self.secret_ref) or None

    def status(self) -> IntegrationStatus:
        """Estado honesto de la fuente."""
        if not self.enabled:
            return IntegrationStatus.DISABLED
        if not self.dsn():
            return IntegrationStatus.PREPARED_NOT_CONNECTED
        return IntegrationStatus.CONNECTED_AND_VALIDATED


class SourcesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    sources: list[SourceConfig] = Field(default_factory=list)


@dataclass(frozen=True)
class SourceCatalog:
    """Catalogo consultable de fuentes."""

    sources: dict[str, SourceConfig]

    def get(self, name: str) -> SourceConfig | None:
        return self.sources.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.sources))

    def enabled_names(self) -> tuple[str, ...]:
        return tuple(sorted(n for n, s in self.sources.items() if s.enabled))

    def status_report(self) -> list[dict[str, str]]:
        return [
            {
                "name": source.name,
                "engine": source.engine,
                "status": str(source.status()),
                "secret_ref": source.secret_ref,
            }
            for source in sorted(self.sources.values(), key=lambda s: s.name)
        ]


def load_sources(path: Path | None = None) -> SourceCatalog:
    """Carga y valida el YAML de fuentes."""
    target = path or get_settings().structured_sources_path
    if not target.exists():
        logger.warning("structured.sources_file_missing", extra={"sources_path": str(target)})
        return SourceCatalog(sources={})
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        parsed = SourcesFile.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise ConfigurationError(
            f"El archivo de fuentes estructuradas es invalido: {target.name}", detail=str(exc)
        ) from exc
    return SourceCatalog(sources={s.name: s for s in parsed.sources})


@lru_cache(maxsize=1)
def get_source_catalog() -> SourceCatalog:
    return load_sources()


def refresh_source_catalog() -> SourceCatalog:
    get_source_catalog.cache_clear()
    return get_source_catalog()
