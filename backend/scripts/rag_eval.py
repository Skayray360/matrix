# Creado por Aldo Garcia.
"""Evaluacion del RAG contra el golden set sintetico (seccion 20).

Metricas producidas:

* ``retrieval_hit_rate``   -- fraccion de casos ``grounded`` cuya evidencia top
  incluye la categoria esperada;
* ``source_correctness``   -- fraccion de casos cuya evidencia proviene EN SU
  TOTALIDAD de categorias autorizadas y esperadas;
* ``grounded_answer_rate`` -- fraccion de respuestas verificadas como
  fundamentadas (solo en modo ``--full``);
* ``unsupported_claim_rate`` -- fraccion de casos ``unsupported`` en los que el
  sistema afirmo algo en lugar de declarar insuficiencia;
* ``acl_leakage_rate``     -- **debe ser 0**: cualquier evidencia de una
  categoria prohibida para ese usuario cuenta como fuga.

Modos:
    --retrieval   solo recuperacion + ACL (rapido, no invoca los LLM de chat)
    --full        recuperacion + generacion + verificacion de grounding

Uso:
    python -m scripts.rag_eval --retrieval --output ../reports/tests/rag_eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from app.agents.orchestrator import Orchestrator
from app.authorization.policy import get_policy_engine
from app.common.ids import new_id
from app.database.engine import session_scope
from app.database.models import User
from app.memory.service import MemoryService
from app.rag.retriever import Retriever

GOLDEN_SET = Path(__file__).resolve().parents[1] / "tests" / "rag_eval" / "golden_set.yaml"

#: Frases con las que el asistente reconoce que no puede responder.
_REFUSAL_MARKERS = (
    "no cuento con informacion",
    "no cuento con información",
    "no tiene acceso",
    "no tengo informacion",
    "no tengo información",
    "evidencia insuficiente",
    "fuera del alcance",
)


@dataclass
class CaseResult:
    case_id: str
    user: str
    case_type: str
    passed: bool
    acl_leak: bool = False
    detail: str = ""
    categories: tuple[str, ...] = ()
    model: str = ""
    latency_ms: int = 0


@dataclass
class EvaluationReport:
    mode: str
    results: list[CaseResult] = field(default_factory=list)

    def metrics(self) -> dict[str, Any]:
        total = len(self.results)
        grounded_cases = [r for r in self.results if r.case_type == "grounded"]
        unsupported_cases = [r for r in self.results if r.case_type == "unsupported"]
        denied_cases = [r for r in self.results if r.case_type == "denied"]

        def rate(passed: int, count: int) -> float:
            return round(100.0 * passed / count, 2) if count else 100.0

        leaks = sum(1 for r in self.results if r.acl_leak)
        return {
            "mode": self.mode,
            "total_cases": total,
            "passed": sum(1 for r in self.results if r.passed),
            "pass_rate_pct": rate(sum(1 for r in self.results if r.passed), total),
            "retrieval_hit_rate_pct": rate(
                sum(1 for r in grounded_cases if r.passed), len(grounded_cases)
            ),
            "source_correctness_pct": rate(
                sum(1 for r in self.results if not r.acl_leak), total
            ),
            "unsupported_claim_rate_pct": rate(
                sum(1 for r in unsupported_cases if not r.passed), len(unsupported_cases)
            ),
            "denied_pass_rate_pct": rate(sum(1 for r in denied_cases if r.passed), len(denied_cases)),
            "acl_leakage_count": leaks,
            "acl_leakage_rate_pct": rate(leaks, total) if total else 0.0,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics(),
            "failures": [
                {
                    "case_id": r.case_id,
                    "user": r.user,
                    "type": r.case_type,
                    "detail": r.detail,
                    "categories": list(r.categories),
                }
                for r in self.results
                if not r.passed
            ],
            "cases": [
                {
                    "case_id": r.case_id,
                    "user": r.user,
                    "type": r.case_type,
                    "passed": r.passed,
                    "acl_leak": r.acl_leak,
                    "categories": list(r.categories),
                    "model": r.model,
                    "latency_ms": r.latency_ms,
                    "detail": r.detail,
                }
                for r in self.results
            ],
        }


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load((path or GOLDEN_SET).read_text(encoding="utf-8")) or {}
    return list(data.get("cases", []))


def _context(db, username: str):  # noqa: ANN001, ANN202
    user = db.execute(select(User).where(User.username == username)).scalar_one()
    return get_policy_engine().build_context(db, user=user, session_id=new_id(), request_id=new_id())


def evaluate_retrieval(cases: list[dict[str, Any]]) -> EvaluationReport:
    """Evalua solo la capa de recuperacion y la ACL. No invoca los LLM de chat."""
    report = EvaluationReport(mode="retrieval")
    retriever = Retriever()
    engine = get_policy_engine()

    with session_scope() as db:
        contexts = {name: _context(db, name) for name in ("Matrix", "MatrixR1")}

        for case in cases:
            started = time.perf_counter()
            ctx = contexts[case["user"]]
            categories = engine.effective_categories(ctx)
            result = retriever.retrieve(
                ctx=ctx,
                question=case["question"],
                authorized_categories=categories,
                comparative=bool(case.get("comparative")),
            )
            found = tuple(sorted({e.category for e in result.evidences}))
            latency = int((time.perf_counter() - started) * 1000)

            forbidden = set(case.get("forbidden_categories", []))
            # Fuga ACL: cualquier evidencia prohibida o fuera del alcance efectivo.
            leak = bool(set(found) & forbidden) or bool(set(found) - set(categories))

            case_type = case["type"]
            if case_type == "grounded":
                expected = case["expected_category"]
                passed = expected in found and not leak
                detail = "" if passed else f"esperada={expected} obtenidas={found}"
            elif case_type == "denied":
                passed = not leak and not (set(found) & forbidden)
                detail = "" if passed else f"evidencia prohibida: {found}"
            else:  # unsupported: no debe haber evidencia relevante
                passed = not leak
                detail = "" if passed else f"evidencia inesperada: {found}"

            report.results.append(
                CaseResult(
                    case_id=case["id"],
                    user=case["user"],
                    case_type=case_type,
                    passed=passed,
                    acl_leak=leak,
                    detail=detail,
                    categories=found,
                    latency_ms=latency,
                )
            )
    return report


def evaluate_full(cases: list[dict[str, Any]]) -> EvaluationReport:
    """Evalua el flujo completo, incluida la sintesis y la verificacion de citas.

    Se abre una sesion de base de datos **por caso**, igual que en produccion cada
    turno de chat es su propio request. Mantener una sola sesion abierta durante
    toda la evaluacion hacia que MySQL cerrara la conexion por inactividad: con
    el modelo profundo un solo caso puede tardar varios minutos y la bateria
    completa, horas.
    """
    report = EvaluationReport(mode="full")
    orchestrator = Orchestrator()
    memory = MemoryService()

    for case in cases:
        with session_scope() as db:
            ctx = _context(db, case["user"])
            conversation = memory.create_conversation(db, ctx, title=f"eval-{case['id']}")
            outcome = orchestrator.handle_chat(
                db, ctx=ctx, conversation=conversation, message=case["question"]
            )

            answer = outcome.answer.lower()
            found = tuple(sorted({e.category for e in outcome.evidences}))
            forbidden = set(case.get("forbidden_categories", []))
            leak = bool(set(found) & forbidden)
            refused = any(marker in answer for marker in _REFUSAL_MARKERS)

            case_type = case["type"]
            if case_type == "grounded":
                keywords = [str(k).lower() for k in case.get("expected_keywords", [])]
                has_keyword = not keywords or any(k in answer for k in keywords)
                passed = (
                    case["expected_category"] in found
                    and outcome.grounded
                    and has_keyword
                    and not leak
                )
                detail = "" if passed else (
                    f"categorias={found} grounded={outcome.grounded} keywords={keywords}"
                )
            elif case_type == "denied":
                # No debe citar la categoria prohibida ni revelar su contenido.
                passed = not leak and not any(term in answer for term in forbidden)
                detail = "" if passed else f"posible fuga: {found}"
            else:  # unsupported
                passed = refused and not leak
                detail = "" if passed else "no declaro insuficiencia"

            report.results.append(
                CaseResult(
                    case_id=case["id"],
                    user=case["user"],
                    case_type=case_type,
                    passed=passed,
                    acl_leak=leak,
                    detail=detail,
                    categories=found,
                    model=outcome.model,
                    latency_ms=outcome.latency_ms,
                )
            )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluacion RAG de Matrix RH")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--retrieval", action="store_true", help="solo recuperacion y ACL (rapido)")
    mode.add_argument("--full", action="store_true", help="incluye generacion y grounding")
    parser.add_argument("--output", default="", help="ruta del reporte JSON")
    parser.add_argument("--limit", type=int, default=0, help="evalua solo los primeros N casos")
    parser.add_argument(
        "--types",
        default="",
        help="filtra por tipo de caso, separado por comas: grounded,denied,unsupported",
    )
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.types:
        wanted = {t.strip() for t in args.types.split(",") if t.strip()}
        cases = [c for c in cases if c["type"] in wanted]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("No hay casos que evaluar con los filtros indicados.")
        return 1

    report = evaluate_full(cases) if args.full else evaluate_retrieval(cases)
    payload = report.as_dict()
    metrics = payload["metrics"]

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    for failure in payload["failures"]:
        print(f"  FALLO {failure['case_id']} ({failure['user']}): {failure['detail']}")

    # Gates: >= 98% de casos y 0 fugas ACL.
    ok = metrics["pass_rate_pct"] >= 98.0 and metrics["acl_leakage_count"] == 0
    print("\nRAG GOLDEN SET:", "APROBADO" if ok else "RECHAZADO")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
