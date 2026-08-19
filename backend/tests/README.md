<!-- Creado por Aldo Garcia. -->

# backend/tests/

| Carpeta | Requiere | Cubre |
|---|---|---|
| `unit/` | nada | Configuración, routing, chunking, loaders, grounding, plan SQL, contexto firmado, redacción, uploads, rate limiting, memoria, agente |
| `integration/` | MySQL | Esquema vs ORM, migraciones, seed, API, sesión, CSRF, ownership |
| `security/` | MySQL | Auth bypass, escalada, IDOR/BOLA, SQLi, uploads maliciosos, rate limiting, secretos, cabeceras |
| `rag_eval/` | Qdrant + Ollama | Golden set: recuperación, corrección de fuente, insuficiencia y fuga ACL |

## Reglas

- Las unitarias no requieren infraestructura.
- Las de integración se **saltan** explícitamente si falta la dependencia, en
  lugar de fallar y contaminar el porcentaje.
- Ningún dato real: todos los fixtures son sintéticos y se generan en memoria.
- No se altera el código productivo para hacer pasar una prueba incorrecta.

## Orden con Qdrant embebido

El almacén embebido admite un solo proceso: ejecute estas suites con el backend
**detenido**.

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m pytest backend\tests -q
```

Los contratos 1.1.0 viven principalmente en
`unit/test_ai_runtime_contracts.py`, `unit/test_access_profile_contract.py`,
`unit/test_entra_role_sync.py`, `unit/test_knowledge_layout.py` y
`unit/test_admin_category_scope.py`.
