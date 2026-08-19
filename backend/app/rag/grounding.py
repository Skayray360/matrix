# Creado por Aldo Garcia.
"""Verificador de grounding y allowlist de fuentes.

Dos garantias que este modulo hace cumplir:

1. **Toda cita debe existir.** Si el modelo cita un ``source_id`` que no estaba
   entre la evidencia recuperada, la sintesis se rechaza. Un source ID inventado
   es indistinguible para el usuario de uno real, y es la forma mas peligrosa de
   alucinacion en un asistente de politicas de RH.
2. **La memoria no es evidencia.** El resumen de la conversacion entra al prompt
   como contexto, nunca como respaldo factual de una politica.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.common.logging import get_logger
from app.rag.schemas import Evidence

logger = get_logger(__name__)

#: Formato de cita esperado en la respuesta del modelo: [[categoria/archivo#n]]
CITATION_RE = re.compile(r"\[\[([^\]]{1,240})\]\]")

#: Frases con las que el asistente reconoce que no tiene respaldo. Si aparecen,
#: la ausencia de citas es correcta y no debe tratarse como fallo de grounding.
_INSUFFICIENCY_MARKERS = (
    "no cuento con informacion",
    "no cuento con información",
    "no tengo informacion",
    "no tengo información",
    "no hay evidencia",
    "evidencia insuficiente",
    "evidencia es insuficiente",
    "informacion insuficiente",
    "información insuficiente",
    "no dispongo de documentos",
    "no encontre informacion",
    "no encontré información",
    "no tiene acceso",
    "fuera del alcance",
)


@dataclass(frozen=True, slots=True)
class GroundingReport:
    """Resultado de verificar una respuesta contra su evidencia."""

    grounded: bool
    cited_source_ids: tuple[str, ...] = field(default_factory=tuple)
    invalid_source_ids: tuple[str, ...] = field(default_factory=tuple)
    declares_insufficiency: bool = False
    reason: str = ""

    @property
    def has_invalid_citations(self) -> bool:
        return bool(self.invalid_source_ids)


def extract_citations(answer: str) -> tuple[str, ...]:
    """Extrae los source IDs citados en el texto."""
    return tuple(dict.fromkeys(m.group(1).strip() for m in CITATION_RE.finditer(answer)))


def declares_insufficiency(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _INSUFFICIENCY_MARKERS)


def verify_grounding(
    answer: str,
    evidences: tuple[Evidence, ...],
    *,
    require_citation: bool = True,
) -> GroundingReport:
    """Valida que cada cita corresponda a evidencia realmente recuperada."""
    allowlist = {e.source_id for e in evidences}
    cited = extract_citations(answer)
    invalid = tuple(sid for sid in cited if sid not in allowlist)
    insufficiency = declares_insufficiency(answer)

    if invalid:
        logger.warning(
            "rag.grounding.invalid_citation",
            extra={"invalid_count": len(invalid), "allowlist_size": len(allowlist)},
        )
        return GroundingReport(
            grounded=False,
            cited_source_ids=cited,
            invalid_source_ids=invalid,
            declares_insufficiency=insufficiency,
            reason="citas fuera de la evidencia recuperada",
        )

    if insufficiency:
        # Reconocer la falta de informacion es una respuesta valida y deseable.
        return GroundingReport(
            grounded=True,
            cited_source_ids=cited,
            declares_insufficiency=True,
            reason="declara insuficiencia de evidencia",
        )

    if require_citation and evidences and not cited:
        return GroundingReport(
            grounded=False,
            cited_source_ids=(),
            declares_insufficiency=False,
            reason="respuesta documental sin ninguna cita",
        )

    if require_citation and not evidences:
        # Sin evidencia, la unica respuesta admisible es declarar insuficiencia.
        return GroundingReport(
            grounded=False,
            cited_source_ids=cited,
            declares_insufficiency=False,
            reason="respuesta afirmativa sin evidencia disponible",
        )

    return GroundingReport(grounded=True, cited_source_ids=cited, reason="ok")


def filter_answer_citations(answer: str, evidences: tuple[Evidence, ...]) -> str:
    """Elimina del texto las citas invalidas como ultima red de seguridad.

    Se usa solo cuando ya se decidio devolver una respuesta degradada: la ruta
    normal ante citas invalidas es regenerar o declarar insuficiencia.
    """
    allowlist = {e.source_id for e in evidences}

    def _replace(match: re.Match[str]) -> str:
        source_id = match.group(1).strip()
        return match.group(0) if source_id in allowlist else ""

    return CITATION_RE.sub(_replace, answer).strip()


def coverage_ratio(answer: str, evidences: tuple[Evidence, ...]) -> float:
    """Fraccion de la evidencia recuperada que la respuesta llega a citar.

    Una cobertura muy baja con evidencia abundante sugiere que la ruta rapida
    ignoro parte del material: es una de las senales que activan la ruta profunda.
    """
    if not evidences:
        return 0.0
    cited = set(extract_citations(answer))
    return len(cited & {e.source_id for e in evidences}) / len(evidences)
