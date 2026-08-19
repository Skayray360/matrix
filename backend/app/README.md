<!-- Creado por Aldo Garcia. -->

# backend/app/

Código de la aplicación, organizado por responsabilidad. Ningún módulo de dominio
importa `api/`.

| Paquete | Responsabilidad |
|---|---|
| `config/` | Configuración tipada y validada; falla el arranque si es insegura |
| `common/` | Errores tipados, logging JSON con redacción, identificadores |
| `database/` | Engine, modelos ORM y runner de migraciones |
| `auth/` | Puerto `IdentityProvider` y adapters `local_test` / `entra`; sesiones |
| `authorization/` | `UserContext` firmado, motor de políticas, registro de categorías |
| `llm/` | Cliente Ollama y política de selección de modelo |
| `rag/` | Chunking, vector store con ACL, recuperación, grounding |
| `ingestion/` | Extractores, servicio de ingesta, reconciliación incremental |
| `structured_data/` | Plan JSON, validador, compilador SQL, adapters read-only |
| `memory/` | Conversaciones, mensajes, resúmenes, contexto filtrado |
| `agents/` | Orquestador, agente de conocimiento, prompts, planificador |
| `security/` | Uploads, rate limiting, defensas de prompt |
| `audit/` | Eventos de auditoría |
| `jobs/` | Scheduler de reconciliación 24 h |
| `api/` | Routers, dependencias, middleware, esquemas |
| `main.py` | Ensamblado de la aplicación |

## Dependencias entre capas

```text
api/ -> agents/ -> rag/, structured_data/, memory/, llm/
api/ -> authorization/, auth/, security/
todos -> database/, common/, config/
```

`common/` y `config/` no dependen de nadie.
