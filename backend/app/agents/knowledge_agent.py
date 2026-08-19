# Creado por Aldo Garcia.
"""Sintesis local con grounding, fallback y resumen jerarquico.

El agente solo recibe evidencia ya autorizada. No conoce el vector store ni el
motor de permisos, por lo que ninguna salida de un modelo puede ampliar el
alcance. Las respuestas documentales se verifican contra una allowlist literal
de ``source_id`` y admiten una sola regeneracion.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.agents.prompts import (
    INSUFFICIENT_ANSWER,
    build_answer_messages,
    build_general_messages,
    build_summary_reduce_messages,
)
from app.common.errors import OllamaUnavailableError
from app.common.logging import get_logger
from app.config import get_settings
from app.llm.model_policy import Intent, ModelPolicy
from app.llm.ollama_client import ChatResult, OllamaClient
from app.memory.service import ConversationContext
from app.rag.grounding import (
    GroundingReport,
    coverage_ratio,
    extract_citations,
    verify_grounding,
)
from app.rag.schemas import Evidence
from app.structured_data.tool import StructuredEvidence

logger = get_logger(__name__)

MIN_COVERAGE_WITH_RICH_EVIDENCE = 0.34
RICH_EVIDENCE_THRESHOLD = 3
_PROMPT_OVERHEAD_TOKENS = 1400
_CHARS_PER_TOKEN_BUDGET = 3


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    """Respuesta sintetizada y metadatos de verificacion."""

    answer: str
    model: str
    latency_ms: int
    grounding: GroundingReport
    regenerated: bool = False
    escalated_to_deep: bool = False
    cited_source_ids: tuple[str, ...] = ()
    hierarchical: bool = False
    map_batches: int = 0


@dataclass(frozen=True, slots=True)
class _FirstPass:
    """Estado de la primera pasada de sintesis, para decidir la regeneracion."""

    result: ChatResult
    report: GroundingReport
    coverage: float
    availability_fallback: bool
    insufficient_coverage: bool
    false_summary_insufficiency: bool


class KnowledgeAgent:
    """Sintetiza sobre evidencia autorizada y ejecuta los dos modelos locales."""

    def __init__(self, *, llm: OllamaClient, policy: ModelPolicy) -> None:
        self._llm = llm
        self._policy = policy

    def answer_general(
        self,
        *,
        question: str,
        memory: ConversationContext | None,
        model_name: str,
    ) -> SynthesisResult:
        """Responde conocimiento general sin presentarlo como politica interna."""
        messages = build_general_messages(question=question, memory=memory)
        result, fallback_used = self._chat_with_fallback(
            model_name=model_name,
            fallback_model_name=self._policy.fallback_for(model_name),
            messages=messages,
            intent=Intent.GENERAL,
        )
        answer = result.content.strip() or (
            "No pude generar una respuesta en este momento con los modelos locales."
        )
        return SynthesisResult(
            answer=answer,
            model=result.model,
            latency_ms=result.latency_ms,
            grounding=GroundingReport(grounded=True, reason="consulta general sin evidencia RH"),
            escalated_to_deep=fallback_used and result.model == self._policy.deep_model,
        )

    def synthesize(
        self,
        *,
        question: str,
        evidences: tuple[Evidence, ...],
        structured: tuple[StructuredEvidence, ...] = (),
        memory: ConversationContext | None = None,
        model_name: str,
        deep_model_name: str | None = None,
        scope_note: str = "",
        intent: Intent = Intent.DOCUMENTAL,
        evidence_truncated: bool = False,
        _allow_hierarchy: bool = True,
    ) -> SynthesisResult:
        """Genera, verifica y como maximo una vez regenera la respuesta."""
        summary_mode = intent is Intent.DOCUMENT_SUMMARY
        if not evidences and not structured:
            return SynthesisResult(
                answer=INSUFFICIENT_ANSWER,
                model=model_name,
                latency_ms=0,
                grounding=GroundingReport(
                    grounded=True, declares_insufficiency=True, reason="sin evidencia autorizada"
                ),
            )

        if summary_mode and _allow_hierarchy and self._summary_exceeds_context(
            evidences, model_name=model_name
        ):
            return self._synthesize_hierarchical_summary(
                question=question,
                evidences=evidences,
                model_name=model_name,
                deep_model_name=deep_model_name,
                scope_note=scope_note,
                evidence_truncated=evidence_truncated,
            )

        messages = build_answer_messages(
            question=question,
            evidences=evidences,
            structured=structured,
            memory=memory,
            scope_note=scope_note,
            document_summary=summary_mode,
        )
        result, availability_fallback = self._chat_with_fallback(
            model_name=model_name,
            fallback_model_name=self._policy.fallback_for(model_name),
            messages=messages,
            intent=intent,
        )
        report = verify_grounding(result.content, evidences, require_citation=bool(evidences))
        coverage = coverage_ratio(result.content, evidences)

        false_summary_insufficiency = summary_mode and bool(evidences) and report.declares_insufficiency
        insufficient_coverage = (
            len(evidences) >= RICH_EVIDENCE_THRESHOLD
            and coverage < MIN_COVERAGE_WITH_RICH_EVIDENCE
            and not report.declares_insufficiency
        )
        needs_retry = not report.grounded or insufficient_coverage or false_summary_insufficiency

        if not needs_retry:
            answer = self._append_limit_notice(result.content, evidence_truncated)
            return SynthesisResult(
                answer=answer,
                model=result.model,
                latency_ms=result.latency_ms,
                grounding=report,
                escalated_to_deep=(
                    availability_fallback and result.model == self._policy.deep_model
                ),
                cited_source_ids=report.cited_source_ids,
            )

        # La primera pasada no quedo fundamentada (o cobertura/insuficiencia
        # falsa): una unica regeneracion, con posible escalado al modelo profundo.
        return self._regenerate(
            question=question,
            evidences=evidences,
            structured=structured,
            memory=memory,
            scope_note=scope_note,
            intent=intent,
            summary_mode=summary_mode,
            evidence_truncated=evidence_truncated,
            deep_model_name=deep_model_name,
            first=_FirstPass(
                result=result,
                report=report,
                coverage=coverage,
                availability_fallback=availability_fallback,
                insufficient_coverage=insufficient_coverage,
                false_summary_insufficiency=false_summary_insufficiency,
            ),
        )

    def _regenerate(
        self,
        *,
        question: str,
        evidences: tuple[Evidence, ...],
        structured: tuple[StructuredEvidence, ...],
        memory: ConversationContext | None,
        scope_note: str,
        intent: Intent,
        summary_mode: bool,
        evidence_truncated: bool,
        deep_model_name: str | None,
        first: _FirstPass,
    ) -> SynthesisResult:
        """Regeneracion unica tras una primera pasada sin grounding suficiente.

        Escala al modelo profundo si el problema es cobertura o insuficiencia
        falsa de resumen. Si la regeneracion tampoco queda fundamentada: para un
        resumen cae a la red extractiva citable; para el resto se descarta la
        salida y se declara insuficiencia (nunca se conservan afirmaciones sin
        respaldo).
        """
        retry_note = self._retry_note(
            first.report,
            first.coverage,
            false_summary_insufficiency=first.false_summary_insufficiency,
        )
        escalate = (
            (first.insufficient_coverage or first.false_summary_insufficiency)
            and deep_model_name is not None
            and deep_model_name != first.result.model
        )
        retry_model = (deep_model_name or first.result.model) if escalate else first.result.model
        logger.info(
            "agent.regenerating",
            extra={
                "reason": first.report.reason or "cobertura insuficiente",
                "coverage": round(first.coverage, 3),
                "escalated": escalate,
                "selected_model": retry_model,
            },
        )
        retry_messages = build_answer_messages(
            question=question,
            evidences=evidences,
            structured=structured,
            memory=memory,
            scope_note=scope_note,
            retry_note=retry_note,
            document_summary=summary_mode,
        )
        retry_result, retry_fallback = self._chat_with_fallback(
            model_name=retry_model,
            fallback_model_name=self._policy.fallback_for(retry_model),
            messages=retry_messages,
            intent=intent,
            retry=True,
        )
        retry_report = verify_grounding(
            retry_result.content, evidences, require_citation=bool(evidences)
        )
        retry_false_insufficiency = (
            summary_mode and bool(evidences) and retry_report.declares_insufficiency
        )
        total_latency = first.result.latency_ms + retry_result.latency_ms

        if retry_report.grounded and not retry_false_insufficiency:
            return SynthesisResult(
                answer=self._append_limit_notice(retry_result.content, evidence_truncated),
                model=retry_result.model,
                latency_ms=total_latency,
                grounding=retry_report,
                regenerated=True,
                escalated_to_deep=(
                    escalate
                    or (first.availability_fallback and first.result.model == self._policy.deep_model)
                    or (retry_fallback and retry_result.model == self._policy.deep_model)
                ),
                cited_source_ids=retry_report.cited_source_ids,
            )

        # Para un resumen con texto legible, dos negativas del modelo no deben
        # convertirse en el falso mensaje que origino esta correccion. Se entrega
        # un resumen extractivo seguro y citable como ultima red.
        if summary_mode:
            return self._extractive_summary(
                evidences,
                model=retry_result.model,
                latency_ms=total_latency,
                evidence_truncated=evidence_truncated,
                regenerated=True,
            )

        if retry_report.has_invalid_citations:
            logger.warning(
                "agent.rejected_fabricated_citations",
                extra={"invalid_count": len(retry_report.invalid_source_ids)},
            )
        # Tras la unica regeneracion, cualquier salida documental sin grounding
        # se descarta completa. Quitar citas invalidas pero conservar afirmaciones
        # sin respaldo violaria el contrato documental estricto.
        return SynthesisResult(
            answer=INSUFFICIENT_ANSWER,
            model=retry_result.model,
            latency_ms=total_latency,
            grounding=retry_report,
            regenerated=True,
            escalated_to_deep=escalate,
        )

    def _chat_with_fallback(
        self,
        *,
        model_name: str,
        fallback_model_name: str,
        messages: list[dict[str, str]],
        intent: Intent,
        retry: bool = False,
    ) -> tuple[ChatResult, bool]:
        """Fallback local acotado para rechazo HTTP especifico del modelo."""
        profile = self._policy.generation_profile(model_name, intent=intent, retry=retry)
        try:
            return (
                self._llm.chat(
                    model=model_name,
                    messages=messages,
                    temperature=profile.temperature,
                    num_ctx=profile.num_ctx,
                    max_tokens=profile.max_tokens,
                ),
                False,
            )
        except OllamaUnavailableError as exc:
            detail = exc.detail or ""
            # Una caida de transporte afecta a ambos modelos en el mismo Ollama;
            # no se duplica. HTTP puede ser modelo ausente u OOM y si justifica
            # probar una sola vez el otro modelo local.
            if not detail.startswith("HTTP ") or fallback_model_name == model_name:
                raise
            logger.warning(
                "llm.model_fallback",
                extra={"primary_model": model_name, "fallback_model": fallback_model_name},
            )
            fallback_profile = self._policy.generation_profile(
                fallback_model_name, intent=intent, retry=retry
            )
            return (
                self._llm.chat(
                    model=fallback_model_name,
                    messages=messages,
                    temperature=fallback_profile.temperature,
                    num_ctx=fallback_profile.num_ctx,
                    max_tokens=fallback_profile.max_tokens,
                ),
                True,
            )

    def _summary_exceeds_context(
        self, evidences: tuple[Evidence, ...], *, model_name: str
    ) -> bool:
        return self._serialized_evidence_chars(evidences) > self._input_budget_chars(
            model_name, Intent.DOCUMENT_SUMMARY
        )

    def _input_budget_chars(self, model_name: str, intent: Intent) -> int:
        profile = self._policy.generation_profile(model_name, intent=intent)
        usable_tokens = max(
            2048, profile.num_ctx - profile.max_tokens - _PROMPT_OVERHEAD_TOKENS
        )
        return usable_tokens * _CHARS_PER_TOKEN_BUDGET

    @staticmethod
    def _serialized_evidence_chars(evidences: tuple[Evidence, ...]) -> int:
        return sum(len(e.text) + 320 for e in evidences)

    def _partition_summary_evidence(
        self, evidences: tuple[Evidence, ...], *, model_name: str
    ) -> tuple[tuple[Evidence, ...], ...]:
        settings = get_settings()
        budget = self._input_budget_chars(model_name, Intent.DOCUMENT_SUMMARY)
        batches: list[tuple[Evidence, ...]] = []
        current: list[Evidence] = []
        current_chars = 0
        for evidence in evidences:
            item_chars = len(evidence.text) + 320
            if current and (
                len(current) >= settings.rag_summary_max_chunks
                or current_chars + item_chars > budget
            ):
                batches.append(tuple(current))
                current = []
                current_chars = 0
            current.append(evidence)
            current_chars += item_chars
        if current:
            batches.append(tuple(current))
        return tuple(batches)

    def _synthesize_hierarchical_summary(
        self,
        *,
        question: str,
        evidences: tuple[Evidence, ...],
        model_name: str,
        deep_model_name: str | None,
        scope_note: str,
        evidence_truncated: bool,
    ) -> SynthesisResult:
        """Map con Gemma y reduce con Qwen solo cuando el contexto no alcanza."""
        fast_budget = self._input_budget_chars(
            self._policy.fast_model, Intent.DOCUMENT_SUMMARY
        )
        # Un chunk configurado excepcionalmente grande puede no caber en Gemma.
        # En ese caso Qwen procesa ese lote; nunca se corta el chunk para forzarlo.
        map_model = (
            self._policy.deep_model
            if any(len(item.text) + 320 > fast_budget for item in evidences)
            else self._policy.fast_model
        )
        reduce_model = deep_model_name or model_name
        batches = self._partition_summary_evidence(evidences, model_name=map_model)

        def summarize_batch(index_and_batch: tuple[int, tuple[Evidence, ...]]) -> SynthesisResult:
            index, batch = index_and_batch
            return self.synthesize(
                question=(
                    f"Resume la parte {index + 1} de {len(batches)} del contenido, "
                    "con sus temas principales."
                ),
                evidences=batch,
                model_name=map_model,
                deep_model_name=deep_model_name,
                scope_note=scope_note,
                intent=Intent.DOCUMENT_SUMMARY,
                _allow_hierarchy=False,
            )

        workers = min(get_settings().ollama_summary_parallel_batches, len(batches))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="matrix-summary") as pool:
            partial_results = tuple(pool.map(summarize_batch, enumerate(batches)))

        partials = tuple(result.answer for result in partial_results)
        reduce_messages = build_summary_reduce_messages(
            question=question, partial_summaries=partials
        )
        reduce_result, fallback_used = self._chat_with_fallback(
            model_name=reduce_model,
            fallback_model_name=self._policy.fallback_for(reduce_model),
            messages=reduce_messages,
            intent=Intent.DOCUMENT_SUMMARY,
        )
        report = verify_grounding(reduce_result.content, evidences, require_citation=True)
        final_citations = set(report.cited_source_ids)
        covers_every_part = all(
            not extract_citations(partial)
            or bool(final_citations.intersection(extract_citations(partial)))
            for partial in partials
        )
        map_latency = sum(result.latency_ms for result in partial_results)
        total_latency = map_latency + reduce_result.latency_ms

        if report.grounded and not report.declares_insufficiency and covers_every_part:
            return SynthesisResult(
                answer=self._append_limit_notice(reduce_result.content, evidence_truncated),
                model=reduce_result.model,
                latency_ms=total_latency,
                grounding=report,
                escalated_to_deep=(
                    reduce_result.model == self._policy.deep_model or fallback_used
                ),
                cited_source_ids=report.cited_source_ids,
                hierarchical=True,
                map_batches=len(batches),
            )

        # El reduce no puede borrar secciones ni fabricar citas. Si no preserva
        # todas las partes, se devuelve la consolidacion de mapas verificados.
        combined = "Resumen consolidado por secciones:\n\n" + "\n\n".join(partials)
        combined_report = verify_grounding(combined, evidences, require_citation=True)
        if combined_report.grounded and not combined_report.declares_insufficiency:
            return SynthesisResult(
                answer=self._append_limit_notice(combined, evidence_truncated),
                model=reduce_result.model,
                latency_ms=total_latency,
                grounding=combined_report,
                regenerated=True,
                escalated_to_deep=reduce_result.model == self._policy.deep_model,
                cited_source_ids=combined_report.cited_source_ids,
                hierarchical=True,
                map_batches=len(batches),
            )
        return self._extractive_summary(
            evidences,
            model=reduce_result.model,
            latency_ms=total_latency,
            evidence_truncated=evidence_truncated,
            regenerated=True,
            hierarchical=True,
            map_batches=len(batches),
        )

    def _extractive_summary(
        self,
        evidences: tuple[Evidence, ...],
        *,
        model: str,
        latency_ms: int,
        evidence_truncated: bool,
        regenerated: bool,
        hierarchical: bool = False,
        map_batches: int = 0,
    ) -> SynthesisResult:
        lines = ["Resumen extractivo del contenido disponible:"]
        cited: list[str] = []
        extractive_limit = get_settings().rag_summary_max_chunks
        for evidence in evidences[:extractive_limit]:
            compact = re.sub(r"\s+", " ", evidence.text).strip()
            excerpt = compact[:420].rstrip()
            if len(compact) > len(excerpt):
                excerpt = excerpt.rsplit(" ", 1)[0] + "…"
            label = evidence.section or evidence.filename
            lines.append(f"- {label}: {excerpt} [[{evidence.source_id}]]")
            cited.append(evidence.source_id)
        if len(evidences) > extractive_limit:
            lines.append(
                f"Nota: la red extractiva cubre {extractive_limit} de "
                f"{len(evidences)} chunks recuperados; solicite el resumen por secciones "
                "para revisar el resto."
            )
        answer = self._append_limit_notice("\n".join(lines), evidence_truncated)
        return SynthesisResult(
            answer=answer,
            model=model,
            latency_ms=latency_ms,
            grounding=GroundingReport(
                grounded=True,
                cited_source_ids=tuple(cited),
                reason="resumen extractivo de seguridad",
            ),
            regenerated=regenerated,
            cited_source_ids=tuple(cited),
            hierarchical=hierarchical,
            map_batches=map_batches,
        )

    @staticmethod
    def _append_limit_notice(answer: str, truncated: bool) -> str:
        if not truncated:
            return answer
        return (
            answer.rstrip()
            + "\n\nNota: el adjunto supera el limite operativo de chunks para una sola "
            "solicitud; este resumen cubre el material procesado hasta ese limite."
        )

    @staticmethod
    def _retry_note(
        report: GroundingReport,
        coverage: float,
        *,
        false_summary_insufficiency: bool = False,
    ) -> str:
        if false_summary_insufficiency:
            return (
                "La evidencia contiene texto legible. Genera el resumen solicitado en vez de "
                "declarar insuficiencia y cita los source_id proporcionados."
            )
        if report.has_invalid_citations:
            return (
                "La respuesta anterior cito source_id que NO existen en la evidencia. "
                "Usa exclusivamente los source_id literales del bloque EVIDENCIA DOCUMENTAL. "
                "Si algo no esta respaldado, omitelo o declara insuficiencia."
            )
        if report.reason == "respuesta documental sin ninguna cita":
            return (
                "La respuesta anterior no incluyo ninguna cita. Cada afirmacion documental "
                "debe llevar su [[source_id]]."
            )
        if coverage < MIN_COVERAGE_WITH_RICH_EVIDENCE:
            return (
                "La respuesta anterior ignoro parte de la evidencia disponible. Revisa toda la "
                "evidencia y cubre los aspectos relevantes de la pregunta, citando cada uno."
            )
        return (
            "La respuesta anterior no quedo fundamentada en la evidencia. Reformulala usando "
            "solo la evidencia proporcionada, con sus citas."
        )
