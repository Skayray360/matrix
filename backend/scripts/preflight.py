# Creado por Aldo Garcia.
"""Preflight y diagnostico de Matrix RH (seccion 29).

Modulo unico de diagnostico. Los scripts de Windows (BAT/PowerShell) y los de
shell **invocan este modulo**; no duplican logica. Asi el diagnostico que ve el
operador en Windows es exactamente el que ejecutan las pruebas.

Uso:
    python -m scripts.preflight              # comprobacion completa
    python -m scripts.preflight --json       # salida JSON para automatizacion
    python -m scripts.preflight --read-only  # no crea directorios ni conecta a escritura

Codigos de salida:
    0 -> todo correcto (puede haber avisos)
    1 -> al menos una comprobacion obligatoria fallo
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class Check:
    """Resultado de una comprobacion individual."""

    name: str
    status: str
    detail: str = ""
    #: Un check no obligatorio nunca provoca codigo de salida distinto de cero.
    required: bool = True

    @property
    def failed(self) -> bool:
        return self.required and self.status == FAIL


@dataclass
class PreflightReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "", *, required: bool = True) -> None:
        self.checks.append(Check(name=name, status=status, detail=detail, required=required))

    @property
    def ok(self) -> bool:
        return not any(c.failed for c in self.checks)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "failed": [c.name for c in self.checks if c.failed],
            "warnings": [c.name for c in self.checks if c.status == WARN],
            "checks": [asdict(c) for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Comprobaciones
# ---------------------------------------------------------------------------
def check_python(report: PreflightReport) -> None:
    version = sys.version_info
    is_64bit = platform.architecture()[0] == "64bit"
    if version[:2] == (3, 12) and is_64bit:
        report.add("python", OK, f"{platform.python_version()} x64")
    elif version[:2] == (3, 12):
        report.add("python", FAIL, f"{platform.python_version()} no es x64")
    else:
        report.add(
            "python",
            FAIL,
            f"Se requiere Python 3.12 x64; encontrado {platform.python_version()}",
        )


def check_dependencies(report: PreflightReport) -> None:
    required = (
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "pymysql",
        "httpx",
        "argon2",
        "sqlglot",
        "qdrant_client",
        "docx",
        "pypdf",
        "openpyxl",
        "yaml",
        "jwt",
    )
    missing: list[str] = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        report.add("dependencias", FAIL, "faltan: " + ", ".join(missing))
    else:
        report.add("dependencias", OK, f"{len(required)} paquetes presentes")


def check_settings(report: PreflightReport):  # noqa: ANN201
    from app.common.errors import ConfigurationError
    from app.config import get_settings

    try:
        settings = get_settings()
    except ConfigurationError as exc:
        report.add("configuracion", FAIL, exc.detail or exc.message)
        return None
    report.add(
        "configuracion",
        OK,
        f"APP_ENV={settings.app_env} AUTH_PROVIDER={settings.auth_provider}",
    )
    return settings


def check_environment_safety(report: PreflightReport, settings) -> None:  # noqa: ANN001
    """Verifica que el modo local no pueda vivir en produccion."""
    from app.config import AppEnv, AuthProvider

    if settings.app_env is AppEnv.PRODUCTION:
        if settings.local_test_auth_enabled or settings.auth_provider is AuthProvider.LOCAL_TEST:
            report.add(
                "modo_local_en_produccion",
                FAIL,
                "LOCAL_TEST_AUTH_ENABLED/AUTH_PROVIDER=local_test en production",
            )
        else:
            report.add("modo_local_en_produccion", OK, "deshabilitado correctamente")
    else:
        report.add(
            "modo_local_en_produccion",
            OK,
            f"APP_ENV={settings.app_env}: modo local permitido",
        )

    if settings.auth_provider is AuthProvider.ENTRA:
        placeholders = {"", "replace_me"}
        missing = [
            name
            for name, value in (
                ("ENTRA_TENANT_ID", settings.entra_tenant_id),
                ("ENTRA_CLIENT_ID", settings.entra_client_id),
                ("ENTRA_REDIRECT_URI", settings.entra_redirect_uri),
            )
            if value in placeholders
        ]
        report.add(
            "entra_configuracion",
            FAIL if missing else OK,
            "faltan: " + ", ".join(missing) if missing else "configurado",
        )
    else:
        report.add(
            "entra_configuracion",
            WARN,
            "AUTH_PROVIDER=local_test: Entra ID queda PREPARED_NOT_CONNECTED",
            required=False,
        )


def check_ollama(report: PreflightReport, settings) -> None:  # noqa: ANN001
    """Ollama alcanzable, los tres modelos presentes y dimension real = 768."""
    from app.common.errors import MatrixError
    from app.llm.ollama_client import OllamaClient

    client = OllamaClient()
    if not client.ping():
        report.add("ollama", FAIL, f"no alcanzable en {settings.ollama_base_url}")
        report.add("ollama_modelos", FAIL, "no verificable")
        report.add("ollama_embeddings", FAIL, "no verificable")
        report.add("ollama_dimension", FAIL, "no verificable")
        return
    report.add("ollama", OK, settings.ollama_base_url)

    try:
        inventory = client.list_models()
    except MatrixError as exc:
        report.add("ollama_modelos", FAIL, exc.message)
        return

    for label, model in (
        ("gemma", settings.ollama_fast_model),
        ("qwen", settings.ollama_deep_model),
        ("embeddinggemma", settings.ollama_embedding_model),
    ):
        report.add(
            f"modelo_{label}",
            OK if inventory.has(model) else FAIL,
            model if inventory.has(model) else f"{model} NO instalado",
        )

    try:
        dimension = client.probe_embedding_dimension()
    except MatrixError as exc:
        report.add("ollama_embeddings", FAIL, exc.message)
        report.add("ollama_dimension", FAIL, "no verificable")
        return

    report.add("ollama_embeddings", OK, "/api/embed responde")
    expected = settings.ollama_embedding_dimension
    report.add(
        "ollama_dimension",
        OK if dimension == expected else FAIL,
        f"real={dimension} esperada={expected}"
        + ("" if dimension == expected else " -- no se trunca ni se rellena el vector"),
    )


def check_database(report: PreflightReport, *, read_only: bool) -> bool:
    """Comprueba la base interna. Devuelve True si es utilizable por Matrix RH.

    Distingue tres situaciones que antes se confundian en un unico fallo
    generico: servidor inalcanzable, base que **pertenece a otra aplicacion**, y
    migraciones pendientes.
    """
    from app.database.engine import check_database as ping_database

    ok, detail = ping_database()
    report.add("mysql", OK if ok else FAIL, detail)
    if not ok:
        report.add("migraciones", FAIL, "no verificable")
        return False

    # Propiedad de la base ANTES que nada: si es ajena, todo lo demas fallara
    # con errores que no explican la causa.
    try:
        from app.database.migrator import database_ownership_problem

        problema = database_ownership_problem()
    except Exception as exc:  # noqa: BLE001
        problema = f"no verificable ({type(exc).__name__})"

    if problema:
        from sqlalchemy.engine import make_url

        from app.config import get_settings

        nombre = make_url(get_settings().database_url.get_secret_value()).database
        report.add(
            "base_de_datos_propia",
            FAIL,
            f"la base '{nombre}' {problema}. "
            f"Edite DATABASE_URL en .env y use un nombre libre (por ejemplo {nombre}_app).",
        )
        report.add("migraciones", FAIL, "no aplicables sobre una base ajena")
        return False

    report.add("base_de_datos_propia", OK, "la base pertenece a Matrix RH")

    try:
        from app.database.migrator import pending_migrations

        pending = pending_migrations()
        if pending and read_only:
            report.add("migraciones", WARN, "pendientes: " + ", ".join(pending), required=False)
        elif pending:
            report.add(
                "migraciones",
                FAIL,
                "pendientes: " + ", ".join(pending) + ". Ejecute INSTALAR_MATRIX_RH.bat",
            )
        else:
            report.add("migraciones", OK, "al dia")
    except Exception as exc:  # noqa: BLE001
        report.add("migraciones", FAIL, type(exc).__name__)
    return True


def check_seed_users(report: PreflightReport, settings, *, database_ok: bool = True) -> None:  # noqa: ANN001
    """Verifica las cuentas sinteticas y que su hash sea Argon2id."""
    if not settings.is_local_auth_allowed:
        report.add("usuarios_prueba", OK, "modo local deshabilitado: no aplica", required=False)
        return
    if not database_ok:
        # Sin una base utilizable, consultar los usuarios produce un error de SQL
        # que no explica nada. Se reporta la dependencia real.
        report.add(
            "usuarios_prueba",
            WARN,
            "no verificable: resuelva antes el problema de la base de datos",
            required=False,
        )
        return
    try:
        from sqlalchemy import select

        from app.auth.passwords import is_argon2id
        from app.database.engine import session_scope
        from app.database.models import LocalCredential, User

        with session_scope() as db:
            problems: list[str] = []
            for username in ("Matrix", "MatrixR1"):
                user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
                if user is None:
                    problems.append(f"{username}: no existe")
                    continue
                credential = db.get(LocalCredential, user.id)
                if credential is None:
                    problems.append(f"{username}: sin credencial local")
                elif not is_argon2id(credential.password_hash_argon2id):
                    problems.append(f"{username}: el hash no es Argon2id")
        if problems:
            report.add("usuarios_prueba", FAIL, "; ".join(problems))
        else:
            report.add("usuarios_prueba", OK, "Matrix y MatrixR1 con hash Argon2id")
    except Exception as exc:  # noqa: BLE001
        report.add("usuarios_prueba", FAIL, type(exc).__name__)


def check_qdrant(report: PreflightReport, settings) -> None:  # noqa: ANN001
    try:
        from app.rag.vector_store import get_vector_store

        ok, detail = get_vector_store().health()
        report.add("qdrant", OK if ok else FAIL, detail)
    except Exception as exc:  # noqa: BLE001
        report.add("qdrant", FAIL, type(exc).__name__)


def check_paths(report: PreflightReport, settings, *, read_only: bool) -> None:  # noqa: ANN001
    knowledge = settings.knowledge_root_path
    report.add(
        "knowledge_root",
        OK if knowledge.is_dir() else FAIL,
        str(knowledge) if knowledge.is_dir() else f"no existe: {knowledge}",
    )

    storage = settings.upload_storage_path
    if read_only:
        report.add(
            "almacenamiento_runtime",
            OK if storage.parent.exists() else WARN,
            str(storage),
            required=False,
        )
        return
    try:
        storage.mkdir(parents=True, exist_ok=True)
        probe = storage / ".preflight_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report.add("almacenamiento_runtime", OK, f"escritura verificada en {storage}")
    except Exception as exc:  # noqa: BLE001
        report.add("almacenamiento_runtime", FAIL, f"{type(exc).__name__}: {storage}")


def check_config_files(report: PreflightReport, settings) -> None:  # noqa: ANN001
    from app.authorization.categories import load_category_policy_file
    from app.structured_data.sources import load_sources

    try:
        policy = load_category_policy_file()
        report.add("politica_categorias", OK, f"{len(policy.categories)} categorias declaradas")
    except Exception as exc:  # noqa: BLE001
        report.add("politica_categorias", FAIL, str(exc)[:200])

    try:
        catalog = load_sources()
        statuses = catalog.status_report()
        connected = [s for s in statuses if s["status"] == "CONNECTED_AND_VALIDATED"]
        report.add(
            "fuentes_estructuradas",
            OK,
            f"{len(statuses)} declaradas, {len(connected)} conectadas",
            required=settings.matrix_external_connectors_required,
        )
        for source in statuses:
            report.add(
                f"fuente_{source['name']}",
                OK if source["status"] != "ERROR" else FAIL,
                source["status"],
                required=settings.matrix_external_connectors_required,
            )
    except Exception as exc:  # noqa: BLE001
        report.add("fuentes_estructuradas", FAIL, str(exc)[:200])


def check_frontend(report: PreflightReport) -> None:
    from app.config import PROJECT_ROOT

    dist = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    report.add(
        "frontend_build",
        OK if dist.exists() else WARN,
        str(dist.parent) if dist.exists() else "no compilado (npm run build)",
        required=False,
    )


def check_supply_chain(report: PreflightReport) -> None:
    """Cadena de suministro del frontend (seccion 13 de docs/SECURITY.md).

    Es una comprobacion **obligatoria**: un paquete comprometido en el arbol
    ejecuta codigo con los privilegios del operador. Si no hay arbol instalado
    se degrada a aviso, porque el backend funciona sin el frontend compilado.
    """
    try:
        from scripts.verify_supply_chain import NODE_MODULES, run

        if not NODE_MODULES.is_dir():
            report.add(
                "cadena_de_suministro",
                WARN,
                "frontend/node_modules ausente (ejecute 'npm ci --ignore-scripts')",
                required=False,
            )
            return

        result = run()
        if result.ok:
            avisos = [f for f in result.findings if f.severity == "warning"]
            detalle = f"{result.checked_packages} paquetes verificados"
            if avisos:
                detalle += f", {len(avisos)} con script de instalacion (no ejecutados)"
            report.add("cadena_de_suministro", OK, detalle)
        else:
            report.add(
                "cadena_de_suministro",
                FAIL,
                "; ".join(f"{f.kind}: {f.detail}" for f in result.blocking[:3]),
            )
    except Exception as exc:  # noqa: BLE001
        report.add("cadena_de_suministro", FAIL, type(exc).__name__)


def check_ports(report: PreflightReport, settings) -> None:  # noqa: ANN001
    """Informa si el puerto del backend esta libre u ocupado."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1.0)
        occupied = probe.connect_ex((settings.app_host, settings.app_port)) == 0
    if not occupied:
        report.add("puerto_backend", OK, f"{settings.app_host}:{settings.app_port} libre")
        return
    # Si esta ocupado, se comprueba si quien responde es Matrix RH.
    try:
        import httpx

        response = httpx.get(f"http://{settings.app_host}:{settings.app_port}/health", timeout=3.0)
        mine = response.status_code == 200 and response.json().get("app") == settings.app_name
    except Exception:  # noqa: BLE001
        mine = False
    report.add(
        "puerto_backend",
        OK if mine else WARN,
        "ocupado por Matrix RH" if mine else "ocupado por otro proceso",
        required=False,
    )


def check_windows_scripts(report: PreflightReport) -> None:
    """Comprueba que los BAT apunten a rutas reales del proyecto."""
    from app.config import PROJECT_ROOT

    expected = (
        "INSTALAR_MATRIX_RH.bat",
        "INICIAR_MATRIX_RH.bat",
        "DETENER_MATRIX_RH.bat",
        "DIAGNOSTICO_MATRIX_RH.bat",
    )
    missing = [name for name in expected if not (PROJECT_ROOT / name).exists()]
    report.add(
        "scripts_windows",
        WARN if missing else OK,
        "faltan: " + ", ".join(missing) if missing else f"{len(expected)} scripts presentes",
        required=False,
    )


# ---------------------------------------------------------------------------
def run_preflight(*, read_only: bool = False) -> PreflightReport:
    """Ejecuta todas las comprobaciones."""
    report = PreflightReport()
    check_python(report)
    check_dependencies(report)
    settings = check_settings(report)
    if settings is None:
        return report

    check_environment_safety(report, settings)
    check_ollama(report, settings)
    database_ok = check_database(report, read_only=read_only)
    check_seed_users(report, settings, database_ok=database_ok)
    check_qdrant(report, settings)
    check_paths(report, settings, read_only=read_only)
    check_config_files(report, settings)
    check_frontend(report)
    check_supply_chain(report)
    check_ports(report, settings)
    check_windows_scripts(report)
    return report


def render_text(report: PreflightReport) -> str:
    symbols = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}
    lines = ["", "=== PREFLIGHT MATRIX RH ===", ""]
    for check in report.checks:
        lines.append(f"{symbols[check.status]} {check.name:26s} {check.detail}")
    lines.append("")
    lines.append("RESULTADO: " + ("PREFLIGHT OK" if report.ok else "PREFLIGHT CON FALLOS"))
    if not report.ok:
        lines.append("Fallos obligatorios: " + ", ".join(c.name for c in report.checks if c.failed))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight y diagnostico de Matrix RH")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument(
        "--read-only", action="store_true", help="no crea directorios ni exige migraciones aplicadas"
    )
    parser.add_argument("--output", default="", help="ruta de archivo donde escribir el JSON")
    args = parser.parse_args(argv)

    # El logging JSON estorba en una salida pensada para un operador.
    os.environ.setdefault("APP_LOG_LEVEL", "WARNING")

    report = run_preflight(read_only=args.read_only)
    payload = report.as_dict()

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else render_text(report))
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
