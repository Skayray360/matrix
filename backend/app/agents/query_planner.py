# Creado por Aldo Garcia.
"""Traduccion de lenguaje natural a ``StructuredQueryPlan``.

El modelo rapido propone un plan **en JSON**; Pydantic lo valida y el
``QueryPolicyValidator`` decide si se ejecuta. El modelo nunca ve ni produce SQL.

Si el modelo devuelve algo que no encaja en el esquema, el plan se descarta en
silencio y la consulta continua solo con RAG: es preferible responder con menos
informacion que ejecutar algo que no se pudo validar.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.common.logging import get_logger
from app.llm.ollama_client import OllamaClient
from app.structured_data.schemas import StructuredQueryPlan

logger = get_logger(__name__)

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)

_PLANNER_SYSTEM = """\
Eres un traductor de preguntas a planes de consulta en JSON. NO escribes SQL.

Devuelves EXCLUSIVAMENTE un objeto JSON con esta forma, sin texto adicional y sin
bloques de codigo:

{
  "source": "<nombre de fuente del catalogo>",
  "entity": "<nombre de entidad del catalogo>",
  "fields": ["<columna>", ...],
  "filters": [{"field": "<columna>",
               "operator": "eq|neq|gt|gte|lt|lte|in|like|is_null|is_not_null",
               "value": <escalar o lista>}],
  "aggregations": [{"function": "count|sum|avg|min|max",
                    "field": "<columna o *>",
                    "alias": "<alias>"}],
  "group_by": ["<columna>", ...],
  "sort": [{"field": "<columna>", "direction": "asc|desc"}],
  "limit": <entero 1-200>
}

Reglas:
- Usa unicamente fuentes, entidades y columnas del CATALOGO. Si la pregunta no se
  puede responder con ese catalogo, devuelve exactamente: {"source": ""}
- No inventes columnas ni tablas.
- No incluyas ningun campo fuera de los listados.
- Si usas agregaciones junto con campos, incluye esos campos en group_by.
"""


def _catalog_prompt(catalog: list[dict[str, Any]]) -> str:
    lines: list[str] = ["CATALOGO DISPONIBLE:"]
    for source in catalog:
        lines.append(f"- fuente: {source['source']} ({source.get('description', '')})")
        for entity in source.get("entities", []):
            columns = ", ".join(entity.get("columns", []))
            lines.append(
                f"    entidad: {entity['name']} ({entity.get('description', '')}) | columnas: {columns}"
            )
    return "\n".join(lines)


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Extrae el primer objeto JSON del texto devuelto por el modelo."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.split("\n", 1)[-1] if "\n" in candidate else candidate
    match = _JSON_BLOCK_RE.search(candidate)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def build_query_plan(
    *,
    question: str,
    catalog: list[dict[str, Any]],
    llm: OllamaClient,
    model_name: str,
) -> StructuredQueryPlan | None:
    """Devuelve un plan validado estructuralmente, o ``None``."""
    if not catalog:
        return None

    messages = [
        {"role": "system", "content": _PLANNER_SYSTEM},
        {"role": "user", "content": f"{_catalog_prompt(catalog)}\n\nPREGUNTA:\n{question}"},
    ]
    try:
        result = llm.chat(model=model_name, messages=messages, temperature=0.0, max_tokens=600)
    except Exception as exc:  # noqa: BLE001 - una consulta estructurada fallida no rompe el chat
        logger.warning("planner.llm_failed", extra={"error_type": type(exc).__name__})
        return None

    payload = extract_json_object(result.content)
    if not payload or not payload.get("source"):
        logger.info("planner.no_plan")
        return None

    try:
        return StructuredQueryPlan.model_validate(payload)
    except ValidationError as exc:
        # El plan no encaja en el esquema: se descarta. Nunca se "arregla" un plan
        # invalido, porque arreglarlo significaria adivinar la intencion.
        logger.warning("planner.invalid_plan", extra={"error_count": len(exc.errors())})
        return None
