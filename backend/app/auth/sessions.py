# Creado por Aldo Garcia.
"""Gestion de sesiones de servidor.

Modelo: el navegador recibe una cookie ``HttpOnly`` con un token opaco. La base
de datos guarda unicamente el **SHA-256** de ese token, de forma que un volcado
de la tabla no permite reutilizar sesiones vivas.

Cada sesion lleva ademas un token CSRF que el frontend obtiene por ``/me`` y
reenvia en la cabecera ``X-CSRF-Token`` de toda peticion mutante (double submit
con validacion de servidor).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.common.errors import UnauthorizedError
from app.common.ids import new_opaque_token, sha256_text, utcnow_naive
from app.common.logging import get_logger
from app.config import get_settings
from app.database.models import SessionRecord, User

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Datos que la capa HTTP necesita tras crear una sesion."""

    session_id: str
    #: Token en claro: se envia en la cookie y NO se persiste.
    session_token: str
    csrf_token: str


def create_session(
    db: Session, *, user: User, auth_source: str, client_fingerprint: str | None = None
) -> IssuedSession:
    """Crea una sesion nueva. Se llama siempre despues de autenticar.

    Emitir un identificador nuevo en cada login evita la fijacion de sesion: un
    token conocido de antemano por un atacante jamas queda asociado al usuario.
    """
    settings = get_settings()
    token = new_opaque_token(32)
    now = utcnow_naive()
    record = SessionRecord(
        session_token_hash=sha256_text(token),
        user_id=user.id,
        csrf_token=new_opaque_token(24),
        auth_source=auth_source,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
        client_fingerprint=client_fingerprint,
    )
    db.add(record)
    db.flush()
    logger.info("auth.session_created", extra={"user_opaque_id": user.id})
    return IssuedSession(session_id=record.id, session_token=token, csrf_token=record.csrf_token)


def resolve_session(db: Session, token: str | None) -> tuple[SessionRecord, User]:
    """Valida la cookie y devuelve la sesion y su usuario.

    Falla cerrado ante token ausente, desconocido, revocado, expirado o usuario
    desactivado.
    """
    if not token:
        raise UnauthorizedError()

    record = db.execute(
        select(SessionRecord).where(SessionRecord.session_token_hash == sha256_text(token))
    ).scalar_one_or_none()
    if record is None:
        raise UnauthorizedError()

    now = utcnow_naive()
    if record.revoked_at is not None or record.expires_at <= now:
        raise UnauthorizedError("La sesion expiro. Vuelva a iniciar sesion.")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError()

    record.last_seen_at = now
    return record, user


def revoke_session(db: Session, session_id: str) -> None:
    db.execute(
        update(SessionRecord)
        .where(SessionRecord.id == session_id, SessionRecord.revoked_at.is_(None))
        .values(revoked_at=utcnow_naive())
    )


def revoke_all_user_sessions(db: Session, user_id: str) -> int:
    """Usado al desactivar una cuenta o al cambiar permisos criticos."""
    result = db.execute(
        update(SessionRecord)
        .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
        .values(revoked_at=utcnow_naive())
    )
    return int(result.rowcount or 0)


def purge_expired_sessions(db: Session) -> int:
    from sqlalchemy import delete

    result = db.execute(delete(SessionRecord).where(SessionRecord.expires_at < utcnow_naive()))
    return int(result.rowcount or 0)


def cookie_parameters() -> dict[str, object]:
    """Atributos de la cookie de sesion.

    ``HttpOnly`` siempre; ``Secure`` y ``SameSite`` se toman de configuracion y
    son obligatoriamente estrictos en produccion (validado en ``Settings``).
    """
    settings = get_settings()
    return {
        "key": settings.session_cookie_name,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "path": "/",
        "max_age": settings.session_ttl_minutes * 60,
    }
