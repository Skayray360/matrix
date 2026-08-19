<!-- Creado por Aldo Garcia. -->

# backend/scripts/

Scripts operativos. Los BAT y los PowerShell de la raíz **delegan aquí**: la
lógica vive en un solo sitio.

| Script | Qué hace |
|---|---|
| `preflight.py` | Comprobación completa del entorno; `--json`, `--read-only` |
| `bootstrap.py` | `migrate`, `seed`, `ingest`, `setup`, `serve`, `status` |
| `rag_eval.py` | Golden set del RAG; `--retrieval`, `--full`, `--types` |
| `secrets_scan.py` | Escaneo de secretos con clasificación y supresiones auditables |
| `run_quality_gate.py` | Coordina lint, typing, pruebas, SAST, dependencias, RAG y E2E |
| `smoke_authorization.py` | Matriz `Matrix` vs `MatrixR1` de punta a punta |
| `load_entra_mapping.py` | Carga el mapeo de grupos de Entra ID |

## Ejecución

Desde la raíz del proyecto en `cmd.exe`:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.preflight
```

Use `--read-only` para un probe que no aplica migraciones, seeds ni ingesta. En
Windows, `DIAGNOSTICO_MATRIX_RH.bat` ya ejecuta esa variante y añade puertos,
procesos y logs.
