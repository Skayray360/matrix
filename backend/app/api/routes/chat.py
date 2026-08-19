# Creado por Aldo Garcia.
"""Ruta de chat. Punto unico por el que el frontend consulta a Matrix RH."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.agents.orchestrator import Orchestrator
from app.api.deps import get_db, get_user_context, require_csrf
from app.api.schemas import ChatRequest, ChatResponse
from app.authorization.context import UserContext
from app.common.errors import RateLimitedError
from app.common.ids import sha256_text
from app.common.logging import get_logger
from app.config import get_settings
from app.memory.service import MemoryService
from app.security.rate_limit import get_rate_limiter

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])

_orchestrator: Orchestrator | None = None
_memory = MemoryService()


def get_orchestrator() -> Orchestrator:
    """Orquestador perezoso: evita construir clientes al importar el modulo."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_csrf)])
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
) -> ChatResponse:
    """Procesa un turno de conversacion."""
    settings = get_settings()
    limiter = get_rate_limiter()
    if not limiter.check(f"chat:{sha256_text(ctx.user_id)}", limit=settings.rate_limit_chat_per_minute).allowed:
        raise RateLimitedError()

    if payload.conversation_id:
        # Ownership verificado dentro: una conversacion ajena devuelve 404.
        conversation = _memory.get_owned_conversation(db, ctx, payload.conversation_id)
    else:
        conversation = _memory.create_conversation(db, ctx)

    outcome = get_orchestrator().handle_chat(
        db, ctx=ctx, conversation=conversation, message=payload.message
    )
    return ChatResponse(
        conversation_id=outcome.conversation_id,
        message_id=outcome.message_id,
        answer=outcome.answer,
        sources=outcome.public_sources(),
        intent=outcome.intent,
        grounded=outcome.grounded,
        latency_ms=outcome.latency_ms,
    )
