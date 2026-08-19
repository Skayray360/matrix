# Creado por Aldo Garcia.
"""Memoria conversacional.

Garantias (seccion 13):

* cada conversacion pertenece a un usuario y **todas** las rutas verifican
  ownership -- no basta con ocultar la conversacion en la UI;
* jamas se mezclan conversaciones de distintos usuarios;
* al reconstruir el contexto se descartan los turnos que se apoyaron en
  categorias que el rol actual **ya no** tiene autorizadas. Si a un usuario se le
  retira `nomina`, la respuesta que le dimos ayer sobre nomina no puede volver al
  prompt de hoy;
* no se almacena chain-of-thought interno del modelo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.authorization.context import UserContext
from app.common.errors import ForbiddenError, NotFoundError
from app.common.ids import new_id, utcnow_naive
from app.common.logging import get_logger
from app.database.models import Conversation, ConversationMessage, ConversationSummary

logger = get_logger(__name__)

#: Numero de turnos recientes que se envian textualmente al modelo.
DEFAULT_RECENT_TURNS = 6
#: A partir de este numero de mensajes se genera/actualiza un resumen.
SUMMARY_THRESHOLD = 12
#: Longitud maxima del texto de un mensaje que se reenvia al prompt.
MAX_MESSAGE_CHARS_IN_CONTEXT = 1200


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Contexto conversacional ya filtrado por permisos vigentes."""

    conversation_id: str
    summary: str = ""
    turns: tuple[ConversationTurn, ...] = field(default_factory=tuple)
    dropped_turns: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.summary and not self.turns


class MemoryService:
    """CRUD de conversaciones y ensamblado del contexto."""

    # ------------------------------------------------------------ conversacion
    def create_conversation(self, db: Session, ctx: UserContext, *, title: str = "") -> Conversation:
        now = utcnow_naive()
        conversation = Conversation(
            id=new_id(),
            user_id=ctx.user_id,
            title=(title or "Nueva conversacion")[:255],
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()
        return conversation

    def get_owned_conversation(self, db: Session, ctx: UserContext, conversation_id: str) -> Conversation:
        """Recupera una conversacion propia.

        Ante una conversacion de otro usuario se devuelve **404**, no 403: un 403
        confirmaria que el identificador existe, que es exactamente la fuga que
        busca un ataque IDOR/BOLA.
        """
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.deleted_at is not None:
            raise NotFoundError("Conversacion no encontrada.")
        if conversation.user_id != ctx.user_id:
            logger.warning(
                "memory.ownership_violation",
                extra={
                    "user_opaque_id": ctx.user_id,
                    "conversation_id": conversation_id,
                    "authorization_decision": "DENY",
                },
            )
            raise NotFoundError("Conversacion no encontrada.")
        return conversation

    def list_conversations(self, db: Session, ctx: UserContext, *, limit: int = 100) -> list[Conversation]:
        """Solo conversaciones propias, nunca de otros usuarios."""
        return list(
            db.execute(
                select(Conversation)
                .where(Conversation.user_id == ctx.user_id, Conversation.deleted_at.is_(None))
                .order_by(Conversation.updated_at.desc())
                .limit(limit)
            ).scalars().all()
        )

    def delete_conversation(self, db: Session, ctx: UserContext, conversation_id: str) -> Conversation:
        conversation = self.get_owned_conversation(db, ctx, conversation_id)
        conversation.deleted_at = utcnow_naive()
        db.flush()
        return conversation

    def rename_if_untitled(self, db: Session, conversation: Conversation, question: str) -> None:
        """Titula la conversacion con la primera pregunta del usuario."""
        if conversation.title in ("", "Nueva conversacion"):
            conversation.title = (question.strip().splitlines()[0] or "Conversacion")[:120]
            db.flush()

    # ---------------------------------------------------------------- mensajes
    def append_message(
        self,
        db: Session,
        conversation: Conversation,
        *,
        role: str,
        content: str,
        model: str | None = None,
        intent: str | None = None,
        source_ids: tuple[str, ...] = (),
        authorized_categories: tuple[str, ...] = (),
    ) -> ConversationMessage:
        """Persiste un turno.

        ``authorized_categories`` deja constancia del alcance con el que se produjo
        el mensaje: es lo que permite descartarlo despues si los permisos cambian.
        """
        message = ConversationMessage(
            id=new_id(),
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            role=role,
            content=content,
            model=model,
            intent=intent,
            source_ids=list(source_ids) or None,
            authorized_categories=list(authorized_categories) or None,
            created_at=utcnow_naive(),
        )
        db.add(message)
        conversation.updated_at = utcnow_naive()
        db.flush()
        return message

    def list_messages(self, db: Session, conversation_id: str, *, limit: int = 200) -> list[ConversationMessage]:
        """Turnos en orden de llegada.

        Se ordena por ``seq`` y no por ``created_at``: la resolucion del reloj no
        garantiza marcas distintas entre dos inserciones consecutivas, y el hilo
        se mostraria invertido.
        """
        return list(
            db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.seq.asc())
                .limit(limit)
            ).scalars().all()
        )

    # ----------------------------------------------------------------- contexto
    def build_context(
        self,
        db: Session,
        ctx: UserContext,
        conversation: Conversation,
        *,
        authorized_categories: frozenset[str],
        recent_turns: int = DEFAULT_RECENT_TURNS,
    ) -> ConversationContext:
        """Ensambla resumen + ultimos turnos, filtrando lo ya no autorizado."""
        if conversation.user_id != ctx.user_id:
            # Defensa en profundidad: nunca se ensambla contexto ajeno.
            raise ForbiddenError()

        messages = list(
            db.execute(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation.id)
                .order_by(ConversationMessage.seq.desc())
                .limit(recent_turns * 3)
            ).scalars().all()
        )
        messages.reverse()

        turns: list[ConversationTurn] = []
        dropped = 0
        for message in messages:
            used = set(message.authorized_categories or [])
            if used and not used.issubset(authorized_categories):
                # El turno se apoyo en categorias que el rol actual ya no tiene.
                dropped += 1
                continue
            turns.append(
                ConversationTurn(
                    role=message.role,
                    content=message.content[:MAX_MESSAGE_CHARS_IN_CONTEXT],
                )
            )

        summary_row = db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conversation.id)
            .order_by(ConversationSummary.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if dropped:
            logger.info(
                "memory.turns_dropped_by_policy",
                extra={"conversation_id": conversation.id, "dropped_turns": dropped},
            )

        return ConversationContext(
            conversation_id=conversation.id,
            summary=summary_row.summary if summary_row else "",
            turns=tuple(turns[-recent_turns:]),
            dropped_turns=dropped,
        )

    # ----------------------------------------------------------------- resumen
    def needs_summary(self, db: Session, conversation_id: str) -> bool:
        total = db.execute(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
        ).scalar_one()
        last = db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.conversation_id == conversation_id)
            .order_by(ConversationSummary.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        covered = last.message_count if last else 0
        return (total - covered) >= SUMMARY_THRESHOLD

    def store_summary(
        self, db: Session, conversation_id: str, *, summary: str, message_count: int
    ) -> ConversationSummary:
        record = ConversationSummary(
            id=new_id(),
            conversation_id=conversation_id,
            summary=summary.strip()[:8000],
            message_count=message_count,
            created_at=utcnow_naive(),
        )
        db.add(record)
        db.flush()
        return record
