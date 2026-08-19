<!-- Creado por Aldo Garcia. -->

# backend/

Backend de Matrix RH: FastAPI sobre Python 3.12.

| Ruta | Contenido |
|---|---|
| `app/` | Código de la aplicación |
| `migrations/` | Migraciones SQL versionadas e idempotentes |
| `seeds/` | Semillas reproducibles (identidad de prueba) |
| `scripts/` | Preflight, bootstrap, quality gate, evaluación RAG, escaneo de secretos |
| `tests/` | Unit, integración, seguridad y golden set del RAG |
| `pyproject.toml` | Dependencias fijadas y configuración de ruff/mypy/pytest |

## Ejecutar

En Windows use los BAT de la raíz; preparan rutas, entorno y logs. Para una
ejecución manual reproducible desde la raíz del proyecto en `cmd.exe`:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap setup
```

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap serve
```

`setup` modifica la base y el índice (`migrate + seed + ingest`). Para revisar
sin aplicar cambios use `DIAGNOSTICO_MATRIX_RH.bat`, no `setup`.

## Dependencias principales

FastAPI, Pydantic v2, SQLAlchemy 2, PyMySQL, httpx, PyJWT, argon2-cffi, sqlglot,
qdrant-client, python-docx, pypdf, openpyxl, PyYAML.

Extras opcionales para drivers de bases externas: `[oracle]`, `[mssql]`,
`[postgres]`. Reducen la superficie: sólo se instala lo que el entorno usa.
