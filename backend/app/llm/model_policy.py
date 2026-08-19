# Creado por Aldo Garcia.
"""Politica de los dos LLM (seccion 7).

``gemma4:latest`` resuelve la ruta rapida: clasificacion, comprension de la
consulta, preguntas documentales normales y sintesis breve o media.
``qwen3.6:latest`` se reserva para razonamiento profundo.

La decision es **determinista y auditable**: se calcula a partir de senales
explicitas (longitud, marcadores de analisis, numero de categorias implicadas,
uso multiherramienta, confianza de recuperacion) y cada decision registra las
senales que la provocaron. No se usa Qwen "por si acaso": la ruta profunda es
mucho mas cara y solo se activa cuando alguna senal la justifica.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

from app.config import get_settings


class ModelChoice(StrEnum):
    FAST = "fast"
    DEEP = "deep"


class Intent(StrEnum):
    """Intencion detectada por el router."""

    IDENTITY = "identity"
    DOCUMENT_SUMMARY = "document_summary"
    DOCUMENTAL = "documental"
    STRUCTURED = "structured"
    MIXED = "mixed"
    CONVERSATIONAL = "conversational"
    GENERAL = "general"
    OUT_OF_SCOPE = "out_of_scope"


#: Marcadores que piden explicitamente un analisis profundo.
_DEEP_MARKERS = (
    "analisis profundo",
    "análisis profundo",
    "analiza a fondo",
    "compara",
    "comparativa",
    "comparación",
    "comparacion",
    "contradiccion",
    "contradicción",
    "diferencias entre",
    "ventajas y desventajas",
    "evalua",
    "evalúa",
    "razona paso a paso",
    "detalladamente",
    "en profundidad",
    "implicaciones",
)

#: Marcadores de consulta a datos estructurados.
#:
#: Deliberadamente NO incluyen "cuantos"/"cuantas" a secas: en un asistente de RH
#: la inmensa mayoria de las preguntas documentales empiezan asi ("cuantos dias
#: de vacaciones", "cuantos minutos de tolerancia") y clasificarlas como consulta
#: a base de datos las mandaba a la ruta profunda sin ninguna necesidad.
_STRUCTURED_MARKERS = (
    "cuantos empleados",
    "cuántos empleados",
    "cuantas personas",
    "cuántas personas",
    "cuantos trabajadores",
    "cuántos trabajadores",
    "total de empleados",
    "suma de",
    "promedio de",
    "listado de empleados",
    "numero de empleados",
    "número de empleados",
    "headcount",
    "plantilla activa",
    "por departamento",
    "por centro de trabajo",
    "rotacion mensual",
    "rotación mensual",
)

#: Marcadores de charla que no requieren recuperacion.
_CONVERSATIONAL_MARKERS = (
    "hola",
    "buenos dias",
    "buenas tardes",
    "buenas noches",
    "gracias",
    "adios",
    "hasta luego",
)

_IDENTITY_MARKERS = (
    "quien eres",
    "quien sos",
    "como te llamas",
    "cual es tu nombre",
    "dime tu nombre",
    "identificate",
    "presentate",
    "que asistente eres",
)

_SUMMARY_MARKERS = (
    "resume",
    "resumeme",
    "resumelo",
    "resumir",
    "resumen",
    "sintetiza",
    "sintetizalo",
    "sintesis",
    "puntos clave",
    "ideas principales",
    "extracto del",
)

# Una pregunta se considera documental por referencias explicitas a contenido
# interno. El signo de interrogacion por si solo NO basta: antes convertia
# cualquier pregunta general en RAG y provocaba falsos mensajes de insuficiencia.
_DOCUMENTAL_MARKERS = (
    "politica",
    "prestacion",
    "beneficio",
    "vacaciones",
    "aguinaldo",
    "nomina",
    "salario",
    "sueldo",
    "compensacion",
    "horario",
    "jornada",
    "incapacidad",
    "permiso laboral",
    "licencia laboral",
    "reclutamiento",
    "seleccion de personal",
    "capacitacion",
    "relaciones laborales",
    "contrato laboral",
    "despido",
    "finiquito",
    "prima vacacional",
    "dias festivos",
    "recursos humanos",
    "reglamento",
    "procedimiento",
    "requisito interno",
    "manual",
    "norma interna",
    "documento",
    "documentacion",
    "archivo",
    "adjunto",
    "contenido cargado",
    "fuentes",
    "segun la",
    "segun el",
    "que dice",
    "de acuerdo con",
    "me corresponde",
    "nos corresponde",
    "en nuestra empresa",
    "en la empresa",
    "en matrix rh",
)

_LONG_QUERY_CHARS = 320
_MANY_QUESTIONS = 2
_SUMMARY_DEEP_CHUNKS = 4
_SUMMARY_DEEP_CHARS = 10_000


def _normalized(text: str) -> str:
    """Minusculas sin diacriticos para clasificacion estable en espanol."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _contains_phrase(text: str, markers: tuple[str, ...]) -> bool:
    """Busca frases completas; evita ``sintesis`` dentro de ``fotosintesis``."""
    return any(
        re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text) is not None
        for marker in markers
    )


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    """Presupuesto de inferencia efectivo para una llamada local."""

    num_ctx: int
    max_tokens: int
    temperature: float


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Modelo elegido y por que."""

    choice: ModelChoice
    model_name: str
    intent: Intent
    signals: tuple[str, ...] = field(default_factory=tuple)

    def as_audit_dict(self) -> dict[str, object]:
        return {
            "selected_model": self.model_name,
            "model_route": str(self.choice),
            "intent": str(self.intent),
            "routing_signals": list(self.signals),
        }


class ModelPolicy:
    """Decide intencion y modelo. Sin estado: facil de probar unitariamente."""

    def __init__(self) -> None:
        settings = get_settings()
        self.fast_model = settings.ollama_fast_model
        self.deep_model = settings.ollama_deep_model
        self.embedding_model = settings.ollama_embedding_model

    # -------------------------------------------------------------- intencion
    def classify_intent(self, question: str) -> Intent:
        """Clasificacion heuristica previa al router.

        Se hace en codigo y no en el LLM porque una clasificacion determinista es
        auditable, no consume un modelo y no es manipulable por prompt injection.
        El modelo rapido puede refinarla despues, pero nunca puede ampliar el
        alcance de seguridad.
        """
        text = _normalized(question.strip())
        if not text:
            return Intent.CONVERSATIONAL

        if _contains_phrase(text, _IDENTITY_MARKERS):
            return Intent.IDENTITY

        if _contains_phrase(text, _SUMMARY_MARKERS):
            return Intent.DOCUMENT_SUMMARY

        has_structured = any(marker in text for marker in _STRUCTURED_MARKERS)
        has_documental = any(marker in text for marker in _DOCUMENTAL_MARKERS)

        if has_structured and has_documental:
            return Intent.MIXED
        if has_structured:
            return Intent.STRUCTURED
        if len(text) < 80 and any(text.startswith(m) for m in _CONVERSATIONAL_MARKERS):
            return Intent.CONVERSATIONAL
        if has_documental:
            return Intent.DOCUMENTAL
        return Intent.GENERAL

    # ----------------------------------------------------------------- router
    def route(
        self,
        question: str,
        *,
        intent: Intent | None = None,
        categories_in_scope: int = 0,
        multi_tool: bool = False,
        low_retrieval_confidence: bool = False,
        verifier_requested_deep: bool = False,
        evidence_count: int = 0,
        evidence_chars: int = 0,
    ) -> RoutingDecision:
        """Selecciona modelo rapido o profundo segun las senales de la seccion 7."""
        resolved_intent = intent or self.classify_intent(question)
        text = _normalized(question.strip())
        signals: list[str] = []

        if any(marker in text for marker in _DEEP_MARKERS):
            signals.append("deep_marker_in_query")
        if len(question) >= _LONG_QUERY_CHARS:
            signals.append("long_query")
        if question.count("?") > _MANY_QUESTIONS:
            signals.append("multiple_questions")
        if categories_in_scope >= 2 and resolved_intent is not Intent.CONVERSATIONAL:
            signals.append("multi_category_comparison")
        if multi_tool:
            signals.append("multi_tool_flow")
        if low_retrieval_confidence:
            signals.append("low_retrieval_confidence")
        if verifier_requested_deep:
            signals.append("verifier_requested_deep")
        if resolved_intent is Intent.MIXED:
            signals.append("mixed_intent")
        if resolved_intent is Intent.DOCUMENT_SUMMARY and (
            evidence_count > _SUMMARY_DEEP_CHUNKS or evidence_chars > _SUMMARY_DEEP_CHARS
        ):
            signals.append("large_document_summary")

        if signals:
            return RoutingDecision(
                choice=ModelChoice.DEEP,
                model_name=self.deep_model,
                intent=resolved_intent,
                signals=tuple(signals),
            )
        return RoutingDecision(
            choice=ModelChoice.FAST,
            model_name=self.fast_model,
            intent=resolved_intent,
            signals=("fast_path_sufficient",),
        )

    def model_for(self, choice: ModelChoice) -> str:
        return self.deep_model if choice is ModelChoice.DEEP else self.fast_model

    def fallback_for(self, model_name: str) -> str:
        """Devuelve el otro modelo local; nunca introduce proveedores externos."""
        return self.fast_model if model_name == self.deep_model else self.deep_model

    def generation_profile(
        self,
        model_name: str,
        *,
        intent: Intent,
        retry: bool = False,
    ) -> GenerationProfile:
        """Aprovecha cada modelo con un presupuesto apropiado y acotado.

        Gemma conserva una ventana pequena para minimizar TTFT en respuestas
        normales. Qwen recibe la ventana profunda para comparativas y resumenes
        extensos. Los limites son configurables y auditables.
        """
        settings = get_settings()
        deep = model_name == self.deep_model
        if intent in (Intent.GENERAL, Intent.CONVERSATIONAL):
            temperature = 0.25
        elif intent is Intent.DOCUMENT_SUMMARY:
            temperature = 0.08
        else:
            temperature = 0.1
        if retry:
            temperature = 0.03
        return GenerationProfile(
            num_ctx=settings.ollama_deep_num_ctx if deep else settings.ollama_fast_num_ctx,
            max_tokens=(
                settings.ollama_deep_max_tokens if deep else settings.ollama_fast_max_tokens
            ),
            temperature=temperature,
        )


#: Expresion usada por las pruebas para comprobar que ningun modelo cloud se cuela.
FORBIDDEN_MODEL_PATTERN = re.compile(
    r"(gpt-|claude-|gemini-|mistral-api|openai|azure-openai)", re.IGNORECASE
)
