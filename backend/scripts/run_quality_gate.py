# Creado por Aldo Garcia.
"""Quality gate unico de Matrix RH (seccion 21).

Coordina, en este orden:

1. lint (``ruff``)
2. typing (``mypy``)
3. pruebas unitarias
4. pruebas de integracion
5. pruebas de seguridad
6. auditoria de dependencias (``pip-audit``)
7. analisis estatico de seguridad (``bandit``)
8. escaneo de secretos (propio + ``detect-secrets`` si esta disponible)
9. pruebas del frontend (``vitest``)
10. Playwright E2E (solo con ``--with-e2e`` y el backend arriba)
11. evaluacion del RAG
12. resumen de gates

Una herramienta ausente se reporta como ``SKIPPED`` y no se disfraza de PASS.
Ningun paso se "aprueba" ignorando hallazgos.

Uso:
    python -m scripts.run_quality_gate
    python -m scripts.run_quality_gate --fast          # sin RAG completo ni E2E
    python -m scripts.run_quality_gate --with-e2e
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # noqa: S404 - se invocan herramientas de calidad conocidas
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import PROJECT_ROOT

BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
REPORTS = PROJECT_ROOT / "reports"
TEST_REPORTS = REPORTS / "tests"
SECURITY_REPORTS = REPORTS / "security"

# Estados de gate. El linter marca S105 por el nombre "PASS"; no es una
# contrasena sino el veredicto de una comprobacion.
PASS = "PASS"  # noqa: S105
FAIL = "FAIL"
SKIPPED = "SKIPPED"


@dataclass
class GateResult:
    name: str
    status: str
    exit_code: int = 0
    duration_s: float = 0.0
    detail: str = ""
    blocking: bool = True


def _run(command: list[str], *, cwd: Path, name: str, blocking: bool = True) -> GateResult:
    """Ejecuta un comando y traduce su codigo de salida a un resultado de gate."""
    started = time.perf_counter()
    print(f"\n=== {name} ===")
    print("  $ " + " ".join(command))
    try:
        completed = subprocess.run(command, cwd=str(cwd), check=False)  # noqa: S603
    except FileNotFoundError:
        return GateResult(name=name, status=SKIPPED, detail="herramienta no instalada", blocking=blocking)
    duration = round(time.perf_counter() - started, 2)
    status = PASS if completed.returncode == 0 else FAIL
    return GateResult(
        name=name,
        status=status,
        exit_code=completed.returncode,
        duration_s=duration,
        blocking=blocking,
    )


def _python() -> str:
    return sys.executable


def _resolve_tool(name: str) -> str | None:
    """Ruta del ejecutable de una herramienta.

    Se busca **primero en el entorno virtual del proyecto** y solo despues en el
    PATH. Motivo: el gate se invoca con la ruta absoluta del interprete
    (``.venv\\Scripts\\python.exe``), sin activar el venv, asi que su carpeta
    ``Scripts`` no esta en el PATH. ``detect-secrets`` estaba instalado como
    dependencia de desarrollo del propio proyecto y aun asi el gate lo daba por
    ausente.
    """
    scripts_dir = Path(sys.executable).parent
    encontrado = shutil.which(name, path=str(scripts_dir))
    return encontrado or shutil.which(name)


def _tool_available(name: str) -> bool:
    return _resolve_tool(name) is not None


def _launcher(name: str) -> list[str] | None:
    """Comando ejecutable para una herramienta que puede ser un script de shell.

    En Windows ``npm`` es ``npm.cmd``. ``shutil.which`` lo encuentra, pero
    ``subprocess.run(["npm", ...])`` no lo puede lanzar: ``CreateProcess`` no
    ejecuta ``.cmd`` ni ``.bat`` sin interprete, y falla con ``FileNotFoundError``.

    El efecto era peor que un fallo: ``_run`` traducia esa excepcion a
    ``SKIPPED: herramienta no instalada`` y el gate informaba de que npm no
    estaba, en un equipo donde si estaba. Un gate que se salta una comprobacion
    y lo llama "no instalado" miente sobre lo que ha verificado.
    """
    resolved = _resolve_tool(name)
    if resolved is None:
        return None
    if resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", resolved]
    return [resolved]


def build_gates(args: argparse.Namespace) -> list[GateResult]:
    TEST_REPORTS.mkdir(parents=True, exist_ok=True)
    SECURITY_REPORTS.mkdir(parents=True, exist_ok=True)
    results: list[GateResult] = []
    py = _python()

    # 1. lint
    results.append(_run([py, "-m", "ruff", "check", "app", "scripts", "seeds", "tests"],
                        cwd=BACKEND_ROOT, name="lint (ruff)"))

    # 2. typing
    results.append(_run([py, "-m", "mypy", "app"], cwd=BACKEND_ROOT, name="typing (mypy)",
                        blocking=False))

    # 2b. encabezados de autoria (requisito 16)
    results.append(_run([py, "-m", "scripts.verify_headers"], cwd=BACKEND_ROOT,
                        name="encabezados de autoria"))

    # 3. unit
    results.append(_run(
        [py, "-m", "pytest", "tests/unit", "-q",
         "--junitxml", str(TEST_REPORTS / "unit-junit.xml"),
         "--cov=app", "--cov-report", f"xml:{TEST_REPORTS / 'coverage-unit.xml'}"],
        cwd=BACKEND_ROOT, name="pruebas unitarias"))

    # 4. integration
    results.append(_run(
        [py, "-m", "pytest", "tests/integration", "-q",
         "--junitxml", str(TEST_REPORTS / "integration-junit.xml")],
        cwd=BACKEND_ROOT, name="pruebas de integracion"))

    # 5. security tests
    results.append(_run(
        [py, "-m", "pytest", "tests/security", "-q",
         "--junitxml", str(TEST_REPORTS / "security-junit.xml")],
        cwd=BACKEND_ROOT, name="pruebas de seguridad"))

    # 6. dependencias
    results.append(_run([py, "-m", "pip_audit", "--strict", "--progress-spinner", "off"],
                        cwd=BACKEND_ROOT, name="auditoria de dependencias (pip-audit)",
                        blocking=False))

    # 7. SAST
    results.append(_run(
        [py, "-m", "bandit", "-q", "-r", "app", "-x", "tests",
         "-f", "json", "-o", str(SECURITY_REPORTS / "bandit.json")],
        cwd=BACKEND_ROOT, name="SAST (bandit)"))

    # 8. secretos
    results.append(_run(
        [py, "-m", "scripts.secrets_scan", "--allow-env",
         "--output", str(SECURITY_REPORTS / "secrets_scan.json")],
        cwd=BACKEND_ROOT, name="escaneo de secretos"))

    # 8b. cadena de suministro (pnpm): lista de bloqueo, scripts de instalacion,
    # indicadores de compromiso y reproducibilidad. Bloqueante.
    results.append(_run(
        [py, "-m", "scripts.verify_supply_chain",
         "--output", str(SECURITY_REPORTS / "supply_chain.json")],
        cwd=BACKEND_ROOT, name="cadena de suministro (pnpm)"))

    detect = _launcher("detect-secrets")
    if detect:
        # Se excluyen los arboles de dependencias y el estado runtime: no son
        # codigo del proyecto y multiplican el tiempo del gate por decenas.
        results.append(_run([*detect, "scan", "--all-files", "--exclude-files",
                             r"(^|[\\/])(\.venv|node_modules|\.git|var|dist|__pycache__)([\\/]|$)"],
                            cwd=PROJECT_ROOT, name="detect-secrets", blocking=False))
    else:
        results.append(GateResult(name="detect-secrets", status=SKIPPED,
                                  detail="no instalado", blocking=False))

    # 9. frontend
    # pnpm se ejecuta por corepack (`corepack pnpm ...`): usa la version fijada en
    # package.json ("packageManager") sin depender del PATH ni de privilegios.
    corepack = _launcher("corepack")
    if (FRONTEND_ROOT / "node_modules").is_dir() and corepack:
        pnpm = [*corepack, "pnpm"]
        # Vulnerabilidades en lo que realmente se despliega: bloqueante.
        results.append(_run([*pnpm, "audit", "--prod", "--audit-level", "low"],
                            cwd=FRONTEND_ROOT, name="pnpm audit (produccion)"))
        # Vulnerabilidades en herramientas de desarrollo: informativo, pero
        # visible. No se ocultan.
        results.append(_run([*pnpm, "audit"], cwd=FRONTEND_ROOT,
                            name="pnpm audit (incluye dev)", blocking=False))
        results.append(_run([*pnpm, "--silent", "run", "test"], cwd=FRONTEND_ROOT,
                            name="pruebas de frontend (vitest)"))
        results.append(_run([*pnpm, "--silent", "run", "build"], cwd=FRONTEND_ROOT,
                            name="build del frontend (tsc + vite)"))
    else:
        for name in (
            "pnpm audit (produccion)",
            "pnpm audit (incluye dev)",
            "pruebas de frontend (vitest)",
            "build del frontend (tsc + vite)",
        ):
            results.append(GateResult(name=name, status=SKIPPED,
                                      detail="node_modules ausente o corepack no disponible"))

    # 10. E2E
    corepack_e2e = _launcher("corepack")
    if args.with_e2e and corepack_e2e:
        results.append(_run([*corepack_e2e, "pnpm", "exec", "playwright", "test"],
                            cwd=FRONTEND_ROOT, name="Playwright E2E"))
    elif args.with_e2e:
        results.append(GateResult(name="Playwright E2E", status=SKIPPED,
                                  detail="corepack no disponible"))
    else:
        results.append(GateResult(name="Playwright E2E", status=SKIPPED,
                                  detail="use --with-e2e con el backend arriba"))

    # 11. RAG
    rag_args = [py, "-m", "scripts.rag_eval", "--output", str(TEST_REPORTS / "rag_eval.json")]
    rag_args.append("--retrieval" if args.fast else "--full")
    results.append(_run(rag_args, cwd=BACKEND_ROOT, name="evaluacion RAG (golden set)"))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quality gate de Matrix RH")
    parser.add_argument("--fast", action="store_true",
                        help="RAG solo en modo recuperacion (sin generacion)")
    parser.add_argument("--with-e2e", action="store_true",
                        help="incluye Playwright (requiere el backend arriba)")
    parser.add_argument("--output", default=str(REPORTS / "quality-gate.json"))
    args = parser.parse_args(argv)

    results = build_gates(args)

    blocking_failures = [r for r in results if r.status == FAIL and r.blocking]
    advisory_failures = [r for r in results if r.status == FAIL and not r.blocking]

    payload = {
        "project": "Matrix RH",
        "overall": PASS if not blocking_failures else FAIL,
        "blocking_failures": [r.name for r in blocking_failures],
        "advisory_failures": [r.name for r in advisory_failures],
        "gates": [asdict(r) for r in results],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 72)
    print("  RESUMEN DEL QUALITY GATE")
    print("=" * 72)
    for result in results:
        marca = {PASS: "[ OK ]", FAIL: "[FAIL]", SKIPPED: "[SKIP]"}[result.status]
        sufijo = "" if result.blocking else "  (informativo)"
        print(f"  {marca} {result.name:42s} {result.duration_s:>7.2f}s{sufijo}")
    print("=" * 72)
    print(f"  Reporte: {out}")
    print(f"  RESULTADO: {payload['overall']}")
    if advisory_failures:
        print("  Hallazgos informativos que requieren revision del Agente de Ciberseguridad:")
        for result in advisory_failures:
            print(f"    - {result.name}")
    print()

    return 0 if not blocking_failures else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
