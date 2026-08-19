# Creado por Aldo Garcia.
"""Bootstrap operativo compartido.

Los archivos ``.bat`` y ``.ps1`` de la raiz **no contienen logica de negocio**:
llaman a este modulo. De ese modo la instalacion, el arranque, el diagnostico y
la validacion se comportan igual desde Windows, desde shell y desde las pruebas.

Subcomandos:
    migrate    aplica migraciones idempotentes
    seed       crea las cuentas sinteticas (solo development/test)
    ingest     reconcilia el knowledge root
    setup      migrate + seed + ingest
    serve      arranca uvicorn (con preflight previo)
    status     resumen corto del estado del sistema
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def cmd_migrate(_: argparse.Namespace) -> int:
    from app.database.migrator import run_migrations

    applied = run_migrations()
    print(f"Migraciones aplicadas ahora: {applied or '(ninguna, ya estaba al dia)'}")
    return 0


def cmd_seed(_: argparse.Namespace) -> int:
    from app.common.errors import ConfigurationError
    from seeds.identity_seed import run

    try:
        created = run()
    except ConfigurationError as exc:
        print(f"Seed omitido: {exc.message}")
        return 0
    print(f"Usuarios sinteticos creados: {created or '(ya existian)'}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from app.database.engine import session_scope
    from app.ingestion.reconciler import reconcile_with_lock

    with session_scope() as db:
        stats = reconcile_with_lock(db, trigger="cli", force=args.force)
    if stats is None:
        print("Ya hay una reconciliacion en curso. No se hizo nada.")
        return 0
    print(json.dumps(stats.as_dict(), indent=2, ensure_ascii=False))
    return 1 if stats.failures else 0


def cmd_setup(args: argparse.Namespace) -> int:
    """Instalacion idempotente completa."""
    for step in (cmd_migrate, cmd_seed):
        code = step(args)
        if code != 0:
            return code
    if args.skip_ingest:
        print("Ingesta inicial omitida por --skip-ingest.")
        return 0
    return cmd_ingest(args)


def cmd_status(_: argparse.Namespace) -> int:
    from app.config import get_settings
    from app.database.engine import check_database
    from app.llm.ollama_client import OllamaClient
    from app.rag.vector_store import get_vector_store

    settings = get_settings()
    db_ok, db_detail = check_database()
    ollama = OllamaClient()
    ollama_ok = ollama.ping()
    try:
        qdrant_ok, qdrant_detail = get_vector_store().health()
    except Exception as exc:  # noqa: BLE001
        qdrant_ok, qdrant_detail = False, type(exc).__name__

    payload: dict[str, Any] = {
        "app_env": str(settings.app_env),
        "auth_provider": str(settings.auth_provider),
        "database": {"ok": db_ok, "detail": db_detail},
        "ollama": {"ok": ollama_ok, "base_url": settings.ollama_base_url},
        "qdrant": {"ok": qdrant_ok, "detail": qdrant_detail},
        "models": {
            "fast": settings.ollama_fast_model,
            "deep": settings.ollama_deep_model,
            "embedding": settings.ollama_embedding_model,
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if (db_ok and ollama_ok and qdrant_ok) else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Arranca el servidor tras un preflight obligatorio."""
    from app.config import get_settings
    from scripts.preflight import render_text, run_preflight

    if not args.skip_preflight:
        report = run_preflight()
        print(render_text(report))
        if not report.ok:
            print("El backend NO se arranca porque el preflight fallo.")
            return 1

    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=args.host or settings.app_host,
        port=args.port or settings.app_port,
        reload=args.reload,
        log_config=None,  # el logging JSON propio ya esta configurado
        access_log=False,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap operativo de Matrix RH")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="aplica migraciones").set_defaults(func=cmd_migrate)
    sub.add_parser("seed", help="crea usuarios sinteticos").set_defaults(func=cmd_seed)
    sub.add_parser("status", help="estado resumido").set_defaults(func=cmd_status)

    ingest = sub.add_parser("ingest", help="reconcilia el knowledge root")
    ingest.add_argument("--force", action="store_true", help="reindexa aunque el SHA no cambie")
    ingest.set_defaults(func=cmd_ingest)

    setup = sub.add_parser("setup", help="migrate + seed + ingest")
    setup.add_argument("--force", action="store_true")
    setup.add_argument("--skip-ingest", action="store_true")
    setup.set_defaults(func=cmd_setup)

    serve = sub.add_parser("serve", help="arranca el backend")
    serve.add_argument("--host", default="")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument("--skip-preflight", action="store_true")
    serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada.

    Los errores tipados se presentan como un mensaje accionable y un codigo de
    salida, **nunca como un traceback**: el operador ejecuta esto desde un `.bat`,
    donde una traza de Python se convierte en ruido ilegible y el motivo real
    (por ejemplo, "la base pertenece a otra aplicacion") se pierde.
    """
    from app.common.errors import MatrixError

    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except MatrixError as exc:
        print("")
        print(f"ERROR [{exc.code}] {exc.message}")
        if exc.detail:
            print(f"  Detalle tecnico: {exc.detail}")
        print("")
        return 1
    except KeyboardInterrupt:
        print("\nInterrumpido por el operador.")
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
