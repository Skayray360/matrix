# Arquitectura — Matrix RH

> Creado por Aldo Garcia.

---

## 1. Vista general

```mermaid
flowchart TD
    subgraph Navegador
        UI[React + TypeScript]
    end

    subgraph Backend["Backend FastAPI (Python 3.12)"]
        GW[API Gateway]
        AG[Authorization Guard]
        OR[Agente Orquestador]
        KA[Agente Especializado de Conocimiento]
        RT[RAG Tool]
        SD[Structured Data Tool]
        MR[Model Router]
        MM[Memory Manager]
        IS[Ingestion Service]
        SC[Scheduler Service]
        AU[Audit & Observability]
    end

    subgraph Datos
        MY[(MySQL / MariaDB)]
        QD[(Qdrant)]
        FS[/data/knowledge/]
        EXT[(Fuentes externas read-only)]
    end

    subgraph IA["Ollama local"]
        G[gemma4:latest]
        Q[qwen3.6:latest]
        E[embeddinggemma:latest]
    end

    UI -->|cookie HttpOnly same-origin| GW
    GW --> AG
    AG -->|UserContext firmado| OR
    OR --> RT
    OR --> SD
    OR --> KA
    OR --> MR
    OR --> MM
    RT --> QD
    RT --> E
    SD --> EXT
    KA --> MR
    MR --> G
    MR --> Q
    MM --> MY
    AG --> MY
    IS --> FS
    IS --> QD
    IS --> E
    SC --> IS
    AU --> MY
```

---

## 2. Componentes runtime

| # | Componente | Módulo | Responsabilidad |
|---|---|---|---|
| 1 | API / Interface Gateway | `app/api/` | Punto único de entrada. Valida sesión, CSRF, payloads y rate limits |
| 2 | Authorization Guard | `app/authorization/` | Calcula permisos efectivos y entrega un `UserContext` firmado e inmutable |
| 3 | Agente Orquestador | `app/agents/orchestrator.py` | Clasifica intención, selecciona herramientas y modelo, controla el orden, genera traza |
| 4 | Agente de Conocimiento | `app/agents/knowledge_agent.py` | Sintetiza sobre evidencia ya autorizada y verifica grounding |
| 5 | RAG Tool | `app/rag/retriever.py` | Busca sólo en chunks autorizados; devuelve evidencias, scores y metadata |
| 6 | Structured Data Tool | `app/structured_data/` | Plan JSON validado → SQL parametrizado read-only |
| 7 | Model Router / Policy | `app/llm/model_policy.py` | Decide `gemma4` (rápido) o `qwen3.6` (profundo) |
| 8 | Memory Manager | `app/memory/service.py` | Memoria por conversación y usuario, filtrada por permisos vigentes |
| 9 | Ingestion Service | `app/ingestion/` | Descubre, extrae, chunkea, embebe, upsert, manifest |
| 10 | Scheduler Service | `app/jobs/scheduler.py` | Reconciliación cada 24 h con lock y auditoría |
| 11 | Audit & Observability | `app/audit/`, `app/common/logging.py` | Logs JSON redactados y eventos de auditoría |

---

## 3. Flujo de un turno de chat

```mermaid
sequenceDiagram
    participant U as Usuario
    participant GW as API Gateway
    participant AG as Authorization Guard
    participant OR as Orquestador
    participant RT as RAG Tool
    participant QD as Qdrant
    participant KA as Agente Conocimiento
    participant LLM as Ollama
    participant AU as Auditoría

    U->>GW: POST /api/v1/chat (cookie + CSRF)
    GW->>AG: resolver sesión
    AG->>AG: construir y firmar UserContext
    AG-->>OR: UserContext (inmutable)
    OR->>OR: sanear mensaje (contenido no confiable)
    OR->>OR: clasificar intención
    alt identidad
        OR-->>U: "Soy Matrix RH." (sin LLM ni RAG)
    else consulta general
        OR->>LLM: prompt general sin fuentes internas
        LLM-->>OR: respuesta general
    else consulta documental o de datos
        OR->>OR: categorías efectivas (deny-by-default)
        OR->>RT: recuperar (categorías autorizadas)
        RT->>QD: query + filtro ACL en la consulta
        QD-->>RT: fetch_k dentro del alcance
        RT->>RT: dedup + MMR + top_k
        RT-->>OR: evidencia
        alt sin evidencia
            OR-->>U: "Evidencia insuficiente"
        else
            OR->>OR: routing (rápido / profundo)
            OR->>KA: pregunta + evidencia + memoria
            KA->>LLM: prompt con bloques separados
            LLM-->>KA: respuesta
            KA->>KA: verificar citas contra la evidencia
            KA-->>OR: respuesta verificada
            OR->>AU: auditar (modelo, tools, fuentes, decisión, latencia)
            OR-->>U: respuesta + fuentes citadas
        end
    end
```

El punto crítico es el orden: **la autorización ocurre antes de tocar el vector
store y antes de construir el prompt**. No se filtra después.

### Resumen de un archivo adjunto

El adjunto no se mezcla con el corpus corporativo:

1. la API valida extensión, firma del formato, tamaño, rutas internas y límites
   de descompresión;
2. Ingestion Service extrae, chunkea y embebe en la colección privada;
3. cada chunk queda ligado a `owner_user_id + conversation_id`;
4. una petición de resumen hace `scroll` por metadata, sin embedding ni umbral
   semántico, usando ese filtro antes de llamar al modelo;
5. Knowledge Agent resume en una llamada o en map/reduce si el contexto no
   alcanza, verifica citas y sólo entonces devuelve contenido y fuentes;
6. borrar la conversación retira también sus vectores privados.

| Propiedad | Corpus oficial | Adjunto de chat |
|---|---|---|
| Origen | `data/knowledge/general` o `data/knowledge/especializadas` | carga del usuario |
| Colección | `matrix_rh_corporate` | `matrix_rh_private` |
| Filtro | categorías RBAC enumeradas | dueño + conversación |
| Persistencia | hasta baja/versionado documental | vida de la conversación |
| Puede publicarlo | rol con `knowledge.admin` dentro de su alcance | cualquier usuario autenticado |

El árbol y las reglas de publicación se detallan en
[`DOCUMENTATION_GOVERNANCE.md`](DOCUMENTATION_GOVERNANCE.md).

Las consultas de RH y las referencias a políticas/documentos siempre recorren la
ruta documental. Sólo una solicitud general fuera de ese ámbito usa conocimiento
del modelo, con un prompt independiente que impide presentarlo como información
interna. El detalle del router está en [`AI_DESIGN.md`](AI_DESIGN.md).

---

## 4. Decisiones de arquitectura y sus motivos

| Decisión | Motivo | Alternativa descartada |
|---|---|---|
| `UserContext` firmado e inmutable | Ninguna capa posterior puede ampliar permisos; un contexto fabricado no pasa `verify()` | Pasar `user_id` entre funciones |
| Filtro ACL dentro de la consulta a Qdrant | El chunk restringido no llega ni a `fetch_k` | Recuperar y filtrar en Python |
| Plan JSON en lugar de SQL del modelo | Elimina estructuralmente la inyección desde el LLM | Validar la cadena SQL generada |
| Verificación por AST del SQL final | Defensa en profundidad frente a un futuro descuido | Confiar en la construcción |
| Runner de migraciones propio sobre SQL | El instalador Windows debe aplicar el esquema en frío, varias veces, sin estado previo | Alembic |
| Qdrant embebido por defecto | El equipo destino no tiene Docker | Exigir Docker |
| Renderizador Markdown que construye nodos React | XSS imposible por construcción, sin depender de un sanitizador | `dangerouslySetInnerHTML` + DOMPurify |
| Rate limiter en memoria | Un único proceso backend; evita añadir Redis al instalador | Redis |
| Scheduler con hilo + `Event` | Única tarea periódica; interrumpible al apagar; sin dependencias | APScheduler/Celery |
| Sesión de servidor con hash del token | Un volcado de la BD no permite reutilizar sesiones | Guardar el token en claro |
| Estimación de tokens determinista | Reproducible y sin depender del tokenizador del modelo | Tokenizador exacto no expuesto por API |

---

## 5. Stack

**Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PyMySQL, httpx,
PyJWT (validación OIDC), argon2-cffi, sqlglot, qdrant-client, python-docx, pypdf,
openpyxl, PyYAML.

**Frontend**: React 18 + TypeScript + Vite, Vitest + Testing Library, Playwright.

**Datos**: MySQL/MariaDB (estado de la aplicación), Qdrant (vectores),
sistema de archivos (`data/knowledge`).

**IA**: Ollama local con `gemma4:latest`, `qwen3.6:latest`, `embeddinggemma:latest`.

---

## 6. Capas y dependencias

```text
api/  ──────────────► agents/ ──► rag/, structured_data/, memory/, llm/
  │                      │
  ├──► authorization/ ◄──┘
  ├──► auth/
  └──► security/

agents/, rag/, structured_data/, memory/, ingestion/  ──► database/, common/, config/
```

Reglas mantenidas:

- `common/` y `config/` no dependen de nadie.
- Los agentes **no** importan `api/`.
- El Agente de Conocimiento no recibe el motor de políticas ni el vector store:
  sólo objetos `Evidence` ya autorizados. Es una restricción de diseño, no una
  convención.
- Las integraciones externas se consumen por puerto/adapter
  (`IdentityProvider`, `ReadOnlySourceAdapter`).
- La identidad visible «Matrix RH» es un contrato de producto común a ambos
  modelos; cambiar de ruta rápida a profunda no cambia el asistente ni sus ACL.

---

## 7. Topología de despliegue

```mermaid
flowchart LR
    Cliente -->|HTTPS| NX[Nginx / proxy TLS]
    NX -->|HTTP interno| API[Backend FastAPI + frontend estático]
    API --> MY[(MySQL)]
    API --> QD[(Qdrant)]
    API --> OL[Ollama 127.0.0.1:11434]
```

MySQL, Qdrant y Ollama **no se exponen públicamente**. Sólo el proxy es accesible
desde fuera. En el arranque por doble clic (equipo local), el backend sirve
también el frontend en `127.0.0.1:8000` sin proxy; las cabeceras de seguridad se
aplican igualmente desde el backend, por lo que el sistema sigue siendo seguro sin
Nginx delante.
