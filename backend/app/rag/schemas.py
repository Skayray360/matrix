# Creado por Aldo Garcia.
"""Estructuras de datos del RAG.

Los metadatos de cada chunk incluyen los campos de control de acceso
(``category``, ``allowed_roles``, ``allowed_groups``, ``sensitivity``) porque el
filtro de autorizacion forma parte de la *consulta* a Qdrant, no de un filtrado
posterior en Python.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from app.common.ids import utcnow_naive

#: Namespace logico de un chunk.
SCOPE_CORPORATE = "corporate"
SCOPE_CONVERSATION = "conversation"


@dataclass(frozen=True, slots=True)
class ChunkMetadata:
    """Metadata persistida junto al vector (payload de Qdrant)."""

    chunk_id: str
    document_id: str
    document_sha256: str
    filename: str
    relative_path: str
    category: str
    subpath: str
    mime_type: str
    page_or_sheet: str
    section: str
    chunk_index: int
    embedding_model: str
    embedding_dimension: int
    ingestion_version: str
    allowed_roles: tuple[str, ...] = field(default_factory=tuple)
    allowed_groups: tuple[str, ...] = field(default_factory=tuple)
    sensitivity: str = "internal"
    scope: str = SCOPE_CORPORATE
    #: Solo para adjuntos privados: aislan el chunk a un usuario y conversacion.
    owner_user_id: str | None = None
    conversation_id: str | None = None
    created_at: datetime = field(default_factory=utcnow_naive)
    updated_at: datetime = field(default_factory=utcnow_naive)

    def to_payload(self, text: str) -> dict[str, Any]:
        """Payload plano para Qdrant (incluye el texto para poder citar)."""
        payload = asdict(self)
        payload["allowed_roles"] = list(self.allowed_roles)
        payload["allowed_groups"] = list(self.allowed_groups)
        payload["created_at"] = self.created_at.isoformat()
        payload["updated_at"] = self.updated_at.isoformat()
        payload["text"] = text
        return payload

    @property
    def source_id(self) -> str:
        """Identificador citable y verificable de la evidencia."""
        return f"{self.category}/{self.filename}#{self.chunk_index}"


@dataclass(frozen=True, slots=True)
class Chunk:
    """Fragmento listo para embeber e indexar."""

    text: str
    metadata: ChunkMetadata

    @property
    def token_estimate(self) -> int:
        from app.rag.chunking import estimate_tokens

        return estimate_tokens(self.text)


@dataclass(frozen=True, slots=True)
class Evidence:
    """Chunk recuperado junto con su score. Es lo unico que ve el agente."""

    source_id: str
    text: str
    score: float
    category: str
    filename: str
    section: str
    page_or_sheet: str
    document_id: str
    chunk_id: str
    scope: str = SCOPE_CORPORATE

    def citation_label(self) -> str:
        """Etiqueta legible mostrada en la UI."""
        location = f", {self.page_or_sheet}" if self.page_or_sheet else ""
        return f"{self.filename}{location}"

    def to_public_dict(self) -> dict[str, Any]:
        """Vista enviada al frontend. Solo evidencia ya autorizada llega aqui."""
        return {
            "source_id": self.source_id,
            "category": self.category,
            "filename": self.filename,
            "section": self.section,
            "page_or_sheet": self.page_or_sheet,
            "score": round(self.score, 4),
            "label": self.citation_label(),
            "scope": self.scope,
        }
