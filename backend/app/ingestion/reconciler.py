# Creado por Aldo Garcia.
"""Reconciliacion incremental del knowledge root (seccion 10.B).

Recorre recursivamente el arbol de conocimiento y sincroniza el indice:

1. detecta carpetas nuevas -> las registra como categorias con deny-by-default;
2. detecta archivos nuevos;
3. detecta archivos modificados comparando **SHA-256** (no fecha: copiar un
   archivo cambia la fecha sin cambiar el contenido, y editarlo con algunas
   herramientas conserva la fecha);
4. detecta archivos eliminados;
5. reindexa solo lo necesario;
6. elimina los chunks obsoletos;
7. no duplica documentos ni chunks;
8. actualiza el manifest;
9. registra resultados y errores.

El job es idempotente y esta protegido por un lock cooperativo en base de datos
que impide dos reconciliaciones simultaneas.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.authorization.categories import (
    CATEGORY_NAME_RE,
    GENERAL_CATEGORY,
    SPECIALIZED_CONTAINER,
    discover_filesystem_categories,
    refresh_registry,
)
from app.common.ids import new_id, utcnow_naive
from app.common.logging import get_logger
from app.config import get_settings
from app.database.models import Document, IngestionJob, JobLock
from app.ingestion.loaders import supported_extensions
from app.ingestion.service import IngestionService
from app.rag.schemas import SCOPE_CORPORATE

logger = get_logger(__name__)

RECONCILE_LOCK = "knowledge_reconcile"
LOCK_TTL_MINUTES = 60


@dataclass
class ReconcileStats:
    """Resumen del trabajo de reconciliacion."""

    scanned_files: int = 0
    new_documents: int = 0
    updated_documents: int = 0
    unchanged_documents: int = 0
    deleted_documents: int = 0
    new_categories: list[str] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "scanned_files": self.scanned_files,
            "new_documents": self.new_documents,
            "updated_documents": self.updated_documents,
            "unchanged_documents": self.unchanged_documents,
            "deleted_documents": self.deleted_documents,
            "new_categories": self.new_categories,
            "failure_count": len(self.failures),
            "failures": self.failures[:20],
        }


class LockNotAcquired(RuntimeError):
    """Otra reconciliacion esta en curso."""


@contextmanager
def reconcile_lock(db: Session, *, owner: str) -> Iterator[None]:
    """Lock cooperativo con expiracion.

    La expiracion evita que un proceso muerto deje el lock tomado para siempre;
    el TTL es holgado respecto a la duracion tipica del job.
    """
    now = utcnow_naive()
    existing = db.get(JobLock, RECONCILE_LOCK)
    if existing is not None and existing.expires_at > now:
        raise LockNotAcquired(f"Lock '{RECONCILE_LOCK}' tomado por {existing.locked_by}")

    if existing is None:
        db.add(
            JobLock(
                lock_name=RECONCILE_LOCK,
                locked_by=owner,
                locked_at=now,
                expires_at=now + timedelta(minutes=LOCK_TTL_MINUTES),
            )
        )
    else:
        existing.locked_by = owner
        existing.locked_at = now
        existing.expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    db.flush()
    db.commit()
    try:
        yield
    finally:
        db.execute(delete(JobLock).where(JobLock.lock_name == RECONCILE_LOCK))
        db.commit()


def category_from_relative_path(relative_path: Path | str) -> str | None:
    """Clasifica una ruta de conocimiento sin confiar en metadatos del archivo.

    ``general/**`` pertenece siempre a la categoria explicita ``general``.
    ``especializadas/<dominio>/**`` pertenece a ``<dominio>``. El formato
    anterior ``<categoria>/**`` conserva su categoria para permitir una
    migracion gradual y no destructiva.

    Un archivo directo bajo ``especializadas`` se rechaza: asignarle una
    categoria por conveniencia violaria deny-by-default.
    """
    parts = Path(relative_path).parts
    if not parts:
        return None

    first = parts[0].lower()
    if first == GENERAL_CATEGORY:
        return GENERAL_CATEGORY
    if first == SPECIALIZED_CONTAINER:
        if len(parts) < 3:
            return None
        domain = parts[1].lower()
        if domain in (GENERAL_CATEGORY, SPECIALIZED_CONTAINER):
            return None
        return domain if CATEGORY_NAME_RE.match(domain) else None
    return first if CATEGORY_NAME_RE.match(first) else None


def iter_knowledge_files(root: Path) -> Iterator[tuple[Path, str, str]]:
    """Genera ``(ruta_absoluta, ruta_relativa_posix, categoria)``.

    Se aplican las reglas de :func:`category_from_relative_path`. Se ignoran
    archivos en la raiz (no pertenecen a ninguna categoria), archivos directos
    bajo ``especializadas`` (les falta dominio) y extensiones no soportadas.
    """
    if not root.is_dir():
        return
    allowed = supported_extensions()
    for dirpath, dirnames, filenames in os.walk(root):
        # No se desciende a carpetas ocultas ni a directorios de control.
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        current = Path(dirpath)
        try:
            relative_dir = current.relative_to(root)
        except ValueError:  # pragma: no cover - os.walk siempre queda bajo root
            continue
        parts = relative_dir.parts
        if not parts:
            continue  # archivos sueltos en la raiz: se ignoran
        for filename in sorted(filenames):
            if filename.startswith("."):
                continue
            # Los README.md son documentacion del repositorio, no conocimiento
            # corporativo: indexarlos contaminaria las respuestas con metadatos
            # del proyecto.
            if filename.lower() == "readme.md":
                continue
            path = current / filename
            if path.suffix.lower() not in allowed:
                continue
            relative = (relative_dir / filename).as_posix()
            category = category_from_relative_path(relative)
            if category is None:
                logger.warning(
                    "ingestion.knowledge_path_unclassified", extra={"relative_path": relative}
                )
                continue
            yield path, relative, category


def reconcile_knowledge(
    db: Session,
    *,
    service: IngestionService | None = None,
    trigger: str = "manual",
    force: bool = False,
) -> ReconcileStats:
    """Sincroniza indice y disco. Devuelve estadisticas del trabajo."""
    settings = get_settings()
    ingestion = service or IngestionService()
    stats = ReconcileStats()
    root = settings.knowledge_root_path

    job = IngestionJob(
        id=new_id(),
        job_type="reconcile",
        status="running",
        trigger_source=trigger,
        started_at=utcnow_naive(),
    )
    db.add(job)
    db.flush()

    # --- categorias nuevas -------------------------------------------------
    known_before = {
        row for row in db.execute(select(Document.category).distinct()).scalars().all() if row
    }
    for category in discover_filesystem_categories(root):
        if category not in known_before:
            stats.new_categories.append(category)
    if stats.new_categories:
        # La nueva categoria queda registrada y sujeta a deny-by-default hasta que
        # exista una regla explicita (o el wildcard de negocio, que es una regla
        # explicita declarada en la politica del rol administrador).
        refresh_registry()
        logger.info("ingestion.new_categories", extra={"new_categories": stats.new_categories})

    # --- archivos presentes en disco --------------------------------------
    seen_paths = _reconcile_present_files(
        db, ingestion=ingestion, root=root, stats=stats, force=force
    )

    # --- archivos eliminados del disco ------------------------------------
    _reconcile_deleted_files(db, ingestion=ingestion, stats=stats, seen_paths=seen_paths)

    job.status = "failed" if stats.failures else "completed"
    job.finished_at = utcnow_naive()
    job.stats = stats.as_dict()
    if stats.failures:
        job.error_message = f"{len(stats.failures)} archivos fallaron"
    db.commit()

    logger.info("ingestion.reconcile_done", extra=stats.as_dict())
    return stats


def _reconcile_present_files(
    db: Session,
    *,
    ingestion: IngestionService,
    root: Path,
    stats: ReconcileStats,
    force: bool,
) -> set[str]:
    """Ingesta cada archivo presente en disco. Un archivo malo no aborta el job.

    Devuelve el conjunto de rutas vistas, para detectar despues las bajas.
    """
    seen_paths: set[str] = set()
    for absolute, relative, category in iter_knowledge_files(root):
        stats.scanned_files += 1
        seen_paths.add(relative)
        try:
            existed = db.execute(
                select(Document.id).where(
                    Document.scope == SCOPE_CORPORATE, Document.relative_path == relative
                )
            ).scalar_one_or_none()
            outcome = ingestion.ingest_corporate_file(
                db,
                absolute_path=absolute,
                relative_path=relative,
                category=category,
                force=force,
            )
            if outcome.skipped:
                stats.unchanged_documents += 1
            elif existed is None:
                stats.new_documents += 1
            else:
                stats.updated_documents += 1
            db.commit()
        except Exception as exc:  # noqa: BLE001 - un archivo malo no aborta el job
            db.rollback()
            stats.failures.append({"path": relative, "error": type(exc).__name__})
            logger.error(
                "ingestion.file_failed",
                extra={"relative_path": relative, "error_type": type(exc).__name__},
            )
    return seen_paths


def _reconcile_deleted_files(
    db: Session,
    *,
    ingestion: IngestionService,
    stats: ReconcileStats,
    seen_paths: set[str],
) -> None:
    """Da de baja los documentos corporativos cuyo archivo ya no esta en disco."""
    stored = db.execute(
        select(Document).where(
            Document.scope == SCOPE_CORPORATE, Document.deleted_at.is_(None)
        )
    ).scalars().all()
    for document in stored:
        if document.relative_path and document.relative_path not in seen_paths:
            try:
                ingestion.delete_document(db, document)
                stats.deleted_documents += 1
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                stats.failures.append(
                    {"path": document.relative_path, "error": type(exc).__name__}
                )


def reconcile_with_lock(
    db: Session, *, trigger: str = "scheduler", force: bool = False
) -> ReconcileStats | None:
    """Ejecuta la reconciliacion salvo que otra ya este en curso."""
    owner = f"pid:{os.getpid()}"
    try:
        with reconcile_lock(db, owner=owner):
            return reconcile_knowledge(db, trigger=trigger, force=force)
    except LockNotAcquired as exc:
        logger.warning("ingestion.reconcile_skipped", extra={"lock_reason": str(exc)})
        return None
