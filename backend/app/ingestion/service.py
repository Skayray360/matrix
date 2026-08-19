# Creado por Aldo Garcia.
"""Servicio de ingesta: extraer -> chunkear -> embeber -> upsert -> manifest.

Pipeline reproducible (seccion 9):
``discover -> authorize policy metadata -> extract -> normalize -> structural
split -> chunk -> embed -> upsert -> manifest -> verify``

El *manifest* es la propia base interna: ``documents`` guarda el estado actual
(SHA-256, numero de chunks, estado) y ``document_versions`` el historico. Se
eligio la base de datos en lugar de un JSON en disco porque la reconciliacion
necesita consultas por SHA y por ruta, y porque un archivo suelto se desincroniza
en cuanto dos procesos escriben a la vez.

Idempotencia: si el SHA-256 no cambio, no se reindexa. Si cambio, se **borran
primero** los vectores del documento y luego se insertan los nuevos, de modo que
nunca queden chunks obsoletos ni duplicados.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authorization.categories import CategoryPolicy, get_registry, validate_category_name
from app.common.errors import IngestionFailedError
from app.common.ids import new_id, sha256_bytes, utcnow_naive
from app.common.logging import get_logger
from app.config import get_settings
from app.database.models import Document, DocumentAccessPolicy, DocumentVersion
from app.ingestion.loaders import extract_document, mime_for_extension
from app.llm.ollama_client import OllamaClient, get_ollama_client
from app.rag.chunking import ChunkDraft, chunk_blocks
from app.rag.embedding_prompts import format_document
from app.rag.schemas import SCOPE_CONVERSATION, SCOPE_CORPORATE, Chunk, ChunkMetadata
from app.rag.vector_store import VectorStore, get_vector_store
from app.security.upload_guard import assert_safe_relative_path

logger = get_logger(__name__)

#: Version del pipeline. Cambiarla obliga a reindexar (se compara en el manifest).
#: v2 introduce los prefijos de tarea de embeddinggemma en los documentos.
#: v3 hace de los encabezados una frontera estructural del chunking.
INGESTION_VERSION = "3"

#: Lote de textos por llamada a /api/embed. Equilibra memoria y numero de viajes.
EMBED_BATCH_SIZE = 16


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    """Resultado de ingerir un documento."""

    document_id: str
    chunk_count: int
    status: str
    skipped: bool = False
    warnings: tuple[str, ...] = ()


class IngestionService:
    """Ingesta de documentos corporativos y de adjuntos privados."""

    def __init__(
        self,
        *,
        store: VectorStore | None = None,
        llm: OllamaClient | None = None,
    ) -> None:
        self._store = store or get_vector_store()
        self._llm = llm or get_ollama_client()
        self._settings = get_settings()

    # ------------------------------------------------------------------------
    # Corporativo
    # ------------------------------------------------------------------------
    def ingest_corporate_file(
        self,
        db: Session,
        *,
        absolute_path: Path,
        relative_path: str,
        category: str,
        force: bool = False,
    ) -> IngestionOutcome:
        """Ingiere un archivo del knowledge root."""
        safe_relative = assert_safe_relative_path(relative_path)
        safe_category = validate_category_name(category)
        data = absolute_path.read_bytes()
        digest = sha256_bytes(data)

        document = db.execute(
            select(Document).where(
                Document.scope == SCOPE_CORPORATE,
                Document.relative_path == safe_relative,
            )
        ).scalar_one_or_none()

        if (
            document is not None
            and not force
            and document.sha256 == digest
            and document.status == "indexed"
            and document.deleted_at is None
            and document.ingestion_version == INGESTION_VERSION
        ):
            return IngestionOutcome(
                document_id=document.id, chunk_count=document.chunk_count, status="unchanged", skipped=True
            )

        now = utcnow_naive()
        if document is None:
            document = Document(
                id=new_id(),
                scope=SCOPE_CORPORATE,
                category=safe_category,
                filename=absolute_path.name,
                relative_path=safe_relative,
                storage_path=str(absolute_path),
                mime_type=mime_for_extension(absolute_path.suffix),
                size_bytes=len(data),
                sha256=digest,
                status="pending",
                ingestion_version=INGESTION_VERSION,
                created_at=now,
                updated_at=now,
            )
            db.add(document)
            db.flush()
        else:
            document.category = safe_category
            document.filename = absolute_path.name
            document.storage_path = str(absolute_path)
            document.mime_type = mime_for_extension(absolute_path.suffix)
            document.size_bytes = len(data)
            document.sha256 = digest
            document.status = "pending"
            document.deleted_at = None
            document.ingestion_version = INGESTION_VERSION
            document.updated_at = now
            db.flush()

        self._ensure_access_policy(db, document, category=safe_category)
        return self._index_document(db, document=document, data=data, category=safe_category)

    # ------------------------------------------------------------------------
    # Adjunto privado de conversacion
    # ------------------------------------------------------------------------
    def ingest_conversation_attachment(
        self,
        db: Session,
        *,
        data: bytes,
        display_name: str,
        internal_filename: str,
        mime_type: str,
        owner_user_id: str,
        conversation_id: str,
    ) -> IngestionOutcome:
        """Ingiere un adjunto en el namespace privado ``user + conversation``.

        Este documento **no** pertenece a ninguna categoria corporativa y no puede
        recuperarse desde otra conversacion ni por otro usuario: su ACL es la
        pareja (owner_user_id, conversation_id), aplicada como filtro en Qdrant.
        """
        storage_dir = self._settings.upload_storage_path / owner_user_id / conversation_id
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage_path = storage_dir / internal_filename
        storage_path.write_bytes(data)

        now = utcnow_naive()
        document = Document(
            id=new_id(),
            scope=SCOPE_CONVERSATION,
            category=None,
            owner_user_id=owner_user_id,
            conversation_id=conversation_id,
            filename=display_name,
            relative_path=None,
            storage_path=str(storage_path),
            mime_type=mime_type,
            size_bytes=len(data),
            sha256=sha256_bytes(data),
            status="pending",
            ingestion_version=INGESTION_VERSION,
            created_at=now,
            updated_at=now,
        )
        db.add(document)
        db.flush()
        return self._index_document(db, document=document, data=data, category=None)

    # ------------------------------------------------------------------------
    # Núcleo comun
    # ------------------------------------------------------------------------
    def _index_document(
        self, db: Session, *, document: Document, data: bytes, category: str | None
    ) -> IngestionOutcome:
        """Extrae, chunkea, embebe e indexa. Actualiza el manifest."""
        settings = self._settings
        try:
            extracted = extract_document(data, filename=document.filename)
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(getattr(exc, "message", exc))[:500]
            db.flush()
            raise

        if extracted.is_empty:
            document.status = "empty"
            document.chunk_count = 0
            document.error_message = "; ".join(extracted.warnings)[:500] or "sin texto extraible"
            db.flush()
            # Se borran vectores previos: el documento ya no aporta evidencia.
            self._store.delete_document(document.id, scope=document.scope)
            return IngestionOutcome(
                document_id=document.id,
                chunk_count=0,
                status="empty",
                warnings=tuple(extracted.warnings),
            )

        drafts = chunk_blocks(
            extracted.blocks,
            chunk_size_tokens=settings.rag_chunk_size_tokens,
            overlap_tokens=settings.rag_chunk_overlap_tokens,
        )
        if not drafts:
            document.status = "empty"
            db.flush()
            return IngestionOutcome(document_id=document.id, chunk_count=0, status="empty")

        policy = get_registry().get(category) if category else None
        subpath = str(Path(document.relative_path).parent) if document.relative_path else ""

        chunks = self._build_chunks(
            document=document,
            drafts=drafts,
            category=category,
            policy=policy,
            subpath=subpath,
        )
        vectors = self._embed_chunks(chunks)

        # Orden critico: primero se borran los vectores antiguos del documento y
        # despues se insertan los nuevos. Al reves quedarian chunks huerfanos de
        # una version anterior mezclados con los actuales.
        self._store.delete_document(document.id, scope=document.scope)
        written = self._store.upsert_chunks(chunks, vectors)
        if written != len(chunks):
            raise IngestionFailedError(
                "No se indexaron todos los chunks del documento.",
                detail=f"esperados={len(chunks)} escritos={written}",
            )

        document.status = "indexed"
        document.chunk_count = len(chunks)
        document.error_message = "; ".join(extracted.warnings)[:500] or None
        document.updated_at = utcnow_naive()
        db.add(
            DocumentVersion(
                id=new_id(),
                document_id=document.id,
                sha256=document.sha256,
                chunk_count=len(chunks),
                ingested_at=utcnow_naive(),
            )
        )
        db.flush()

        logger.info(
            "ingestion.document_indexed",
            extra={
                "document_id": document.id,
                "category": category,
                "chunk_count": len(chunks),
                "scope": document.scope,
            },
        )
        return IngestionOutcome(
            document_id=document.id,
            chunk_count=len(chunks),
            status="indexed",
            warnings=tuple(extracted.warnings),
        )

    def _build_chunks(
        self,
        *,
        document: Document,
        drafts: list[ChunkDraft],
        category: str | None,
        policy: CategoryPolicy | None,
        subpath: str,
    ) -> list[Chunk]:
        """Construye los chunks con su metadata de ACL a partir de los borradores.

        La ACL (``allowed_groups``/``sensitivity``) sale de la politica de la
        categoria; un documento sin categoria (adjunto privado) queda como
        ``__private__`` con sensibilidad ``private``.
        """
        settings = self._settings
        normalized_subpath = "" if subpath in (".", "") else subpath
        chunks: list[Chunk] = []
        for draft in drafts:
            metadata = ChunkMetadata(
                chunk_id=new_id(),
                document_id=document.id,
                document_sha256=document.sha256,
                filename=document.filename,
                relative_path=document.relative_path or document.filename,
                category=category or "__private__",
                subpath=normalized_subpath,
                mime_type=document.mime_type,
                page_or_sheet=draft.page_or_sheet,
                section=draft.section,
                chunk_index=draft.index,
                embedding_model=settings.ollama_embedding_model,
                embedding_dimension=settings.rag_embedding_dimension,
                ingestion_version=INGESTION_VERSION,
                allowed_roles=(),
                allowed_groups=tuple(policy.allowed_groups) if policy else (),
                sensitivity=policy.sensitivity if policy else "private",
                scope=document.scope,
                owner_user_id=document.owner_user_id,
                conversation_id=document.conversation_id,
            )
            chunks.append(Chunk(text=draft.text, metadata=metadata))
        return chunks

    def _embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Embebe los chunks por lotes con el prefijo de documento.

        Se usa el prefijo de documento de embeddinggemma (la consulta usa el de
        query); ambos deben coincidir con ``INGESTION_VERSION``.
        """
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[start : start + EMBED_BATCH_SIZE]
            vectors.extend(
                self._llm.embed(
                    [
                        format_document(
                            c.text, title=c.metadata.section or c.metadata.filename
                        )
                        for c in batch
                    ]
                )
            )
        return vectors

    def _ensure_access_policy(self, db: Session, document: Document, *, category: str) -> None:
        """Crea/actualiza la politica de acceso del documento a partir de la categoria."""
        policy = get_registry().get(category)
        existing = db.execute(
            select(DocumentAccessPolicy).where(DocumentAccessPolicy.document_id == document.id)
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                DocumentAccessPolicy(
                    id=new_id(),
                    document_id=document.id,
                    allowed_roles=[],
                    allowed_groups=list(policy.allowed_groups),
                    sensitivity=policy.sensitivity,
                    source_owner=policy.source_owner,
                    created_at=utcnow_naive(),
                )
            )
        else:
            existing.allowed_groups = list(policy.allowed_groups)
            existing.sensitivity = policy.sensitivity
            existing.source_owner = policy.source_owner
        db.flush()

    # ------------------------------------------------------------------------
    # Borrado
    # ------------------------------------------------------------------------
    def delete_document(self, db: Session, document: Document) -> None:
        """Retira el documento del indice y lo marca como borrado."""
        self._store.delete_document(document.id, scope=document.scope)
        document.deleted_at = utcnow_naive()
        document.status = "deleted"
        document.chunk_count = 0
        db.flush()
        logger.info("ingestion.document_deleted", extra={"document_id": document.id})

    def delete_conversation_documents(self, db: Session, conversation_id: str) -> int:
        """Al borrar una conversacion se retiran tambien sus vectores temporales."""
        documents = db.execute(
            select(Document).where(
                Document.conversation_id == conversation_id,
                Document.scope == SCOPE_CONVERSATION,
                Document.deleted_at.is_(None),
            )
        ).scalars().all()
        self._store.delete_conversation(conversation_id)
        now = utcnow_naive()
        for document in documents:
            document.deleted_at = now
            document.status = "deleted"
            document.chunk_count = 0
        db.flush()
        return len(documents)
