# Creado por Aldo Garcia.
"""Logging estructurado JSON con redaccion obligatoria.

Cada linea de log es un objeto JSON con los campos definidos en la seccion 19 de
la especificacion. La redaccion se hace en el formatter (no en los llamadores)
para que sea imposible saltarsela por descuido.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.common.redaction import redact_value

#: Contexto por request. Se propaga a todos los logs emitidos durante el request
#: sin obligar a pasar el request_id por parametro en cada funcion.
#: El valor por defecto es ``None`` (no un dict): un contenedor mutable como
#: default de un ContextVar se comparte entre contextos y acabaria mezclando
#: campos de requests distintos en los logs.
request_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "matrix_request_context", default=None
)


def _current_context() -> dict[str, Any]:
    return request_context.get() or {}

#: Atributos internos de ``logging.LogRecord`` que no deben duplicarse.
_RESERVED = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"asctime", "message", "taskName"}
)


class JsonFormatter(logging.Formatter):
    """Serializa cada registro como JSON de una sola linea, ya redactado."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_current_context())
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            # Solo el tipo y el mensaje: el traceback completo puede contener
            # fragmentos de prompts o de filas de BD.
            exc_type, exc_value, _ = record.exc_info
            payload["error_type"] = getattr(exc_type, "__name__", str(exc_type))
            payload["error_message"] = str(exc_value)
        safe = redact_value(payload)
        return json.dumps(safe, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Instala el formatter JSON como unico handler de la raiz."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Uvicorn duplica los mensajes de acceso; se delega todo a la raiz.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore"):
        logger = logging.getLogger(noisy)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def bind_request_context(**fields: Any) -> contextvars.Token[dict[str, Any] | None]:
    """Agrega campos al contexto del request actual."""
    current = dict(_current_context())
    current.update({k: v for k, v in fields.items() if v is not None})
    return request_context.set(current)


def reset_request_context(token: contextvars.Token[dict[str, Any] | None]) -> None:
    request_context.reset(token)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
