<!-- Creado por Aldo Garcia. -->

# app/config/

Configuración tipada de Matrix RH (`pydantic-settings`).

## Por qué todo vive aquí

La sección 9 de la especificación exige que los parámetros operativos sean
**auditables** y no queden enterrados en constantes dispersas. `Settings` es la
única fuente de verdad y `rag_parameters_snapshot()` la expone en
`/api/v1/admin/diagnostics`.

## Invariantes que impiden el arranque

- `chunk_size > overlap`, `fetch_k >= top_k`, `0 <= mmr_lambda <= 1`
- `RAG_EMBEDDING_DIMENSION == OLLAMA_EMBEDDING_DIMENSION`
- Con `APP_ENV=production`: `AUTH_PROVIDER != local_test`,
  `LOCAL_TEST_AUTH_ENABLED=false`, `LOCAL_TEST_SEED_USERS_ENABLED=false`,
  `SESSION_COOKIE_SECURE=true`, `APP_SECRET_KEY` presente
- Con `AUTH_PROVIDER=entra`: tenant, client y redirect URI configurados

## Entradas / salidas

**Entrada**: variables de entorno y `.env` de la raíz.
**Salida**: instancia única `get_settings()` cacheada.

Los secretos usan `SecretStr`: no aparecen en `repr()` ni en logs.
