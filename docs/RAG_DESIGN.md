# Diseño del RAG — Matrix RH

> Creado por Aldo Garcia.

Este documento describe el RAG **tal como está implementado**. Cada parámetro
indica el archivo y la clase donde vive, para que documentación y código no
puedan divergir. El mismo conjunto se expone en runtime en
`GET /api/v1/admin/diagnostics` (requiere permiso `diagnostics.read`).

---

## 1. Parámetros efectivos

| Parámetro | Valor | Dónde vive en el código |
|---|---|---|
| `RAG_VECTOR_STORE` | `qdrant` | `backend/app/config/settings.py::Settings.rag_vector_store` |
| `RAG_CHUNK_SIZE_TOKENS` | `900` | `Settings.rag_chunk_size_tokens` |
| `RAG_CHUNK_OVERLAP_TOKENS` | `120` | `Settings.rag_chunk_overlap_tokens` |
| `RAG_EMBEDDING_DIMENSION` | `768` | `Settings.rag_embedding_dimension` |
| `RAG_TOP_K` | `6` | `Settings.rag_top_k` |
| `RAG_FETCH_K` | `24` | `Settings.rag_fetch_k` |
| `RAG_MIN_SIMILARITY` | `0.35` | `Settings.rag_min_similarity` |
| `RAG_MMR_LAMBDA` | `0.65` | `Settings.rag_mmr_lambda` |
| `RAG_SEARCH_STRATEGY` | `cosine_hnsw_metadata_filter_mmr` | `Settings.rag_search_strategy` |
| `RAG_REINDEX_INTERVAL_HOURS` | `24` | `Settings.rag_reindex_interval_hours` |
| Modelo de embeddings | `embeddinggemma:latest` | `Settings.ollama_embedding_model` |
| Modelo rápido | `gemma4:latest` | `Settings.ollama_fast_model` |
| Modelo profundo | `qwen3.6:latest` | `Settings.ollama_deep_model` |
| `OLLAMA_FAST_NUM_CTX` | `8192` | `Settings.ollama_fast_num_ctx` |
| `OLLAMA_DEEP_NUM_CTX` | `32768` | `Settings.ollama_deep_num_ctx` |
| `OLLAMA_FAST_MAX_TOKENS` | `768` | `Settings.ollama_fast_max_tokens` |
| `OLLAMA_DEEP_MAX_TOKENS` | `2048` | `Settings.ollama_deep_max_tokens` |
| `OLLAMA_KEEP_ALIVE` | `15m` | `Settings.ollama_keep_alive` |
| `OLLAMA_EMBEDDING_CACHE_SIZE` | `256` | `Settings.ollama_embedding_cache_size` |
| `OLLAMA_SUMMARY_PARALLEL_BATCHES` | `2` | `Settings.ollama_summary_parallel_batches` |
| `RAG_SUMMARY_SCAN_MAX_CHUNKS` | `256` | `Settings.rag_summary_scan_max_chunks` |
| `RAG_SUMMARY_MAX_CHUNKS` | `24` | `Settings.rag_summary_max_chunks` |
| Margen de baja confianza | `0.05` sobre `RAG_MIN_SIMILARITY` | `backend/app/rag/retriever.py::LOW_CONFIDENCE_MARGIN` |
| Corte estructural por encabezado | `80` tokens mínimos | `backend/app/rag/chunking.py::HEADING_BREAK_MIN_TOKENS` |
| Versión del pipeline | `3` | `backend/app/ingestion/service.py::INGESTION_VERSION` |

### Validaciones que impiden el arranque

Implementadas en `Settings._validate_rag_invariants`:

- `chunk_size > overlap`
- `fetch_k >= top_k`
- `top_k >= 1` (por tipo `Field(ge=1)`)
- `0 <= mmr_lambda <= 1`
- `RAG_EMBEDDING_DIMENSION == OLLAMA_EMBEDDING_DIMENSION`
- `RAG_SUMMARY_SCAN_MAX_CHUNKS >= RAG_SUMMARY_MAX_CHUNKS`

Y en runtime, `OllamaClient.embed` comprueba la dimensión **real** de cada
vector. Si no coincide lanza `EmbeddingDimensionMismatchError`. **Nunca se trunca
ni se rellena un vector.**

---

## 2. Vector store

**Qdrant**, por cinco razones funcionales concretas:

1. **Persistencia** en disco entre reinicios.
2. **Búsqueda por coseno** nativa.
3. **Filtros de metadata evaluados dentro del motor**, lo que permite aplicar la
   ACL *antes* de que ningún chunk salga hacia el LLM. Ésta es la razón
   determinante: un vector store sin filtros obligaría a recuperar primero y
   filtrar después, que es exactamente lo que la política prohíbe.
4. **Colecciones separadas** para corpus corporativo y adjuntos privados.
5. **Operación local** y contenerizable.

### Modos

| Modo | Uso | Configuración |
|---|---|---|
| `embedded` (por defecto) | Almacenamiento local persistente del cliente oficial de Qdrant. Sin Docker. | `QDRANT_MODE=embedded`, `QDRANT_PATH=./var/qdrant` |
| `server` | Instancia Qdrant dedicada por HTTP. | `QDRANT_MODE=server`, `QDRANT_URL`, `QDRANT_API_KEY` |

**No existe fallback silencioso.** Si el modo configurado no está operativo,
`VectorStore.health()` falla, `/ready` devuelve 503 y las consultas RAG devuelven
`qdrant_unavailable`.

> **Limitación conocida del modo `embedded`**: el almacenamiento local admite un
> único proceso. Mientras el backend esté arriba, un script que acceda
> directamente al índice fallará con un mensaje explícito. Por eso
> `windows\Validate-MatrixRH.ps1` ejecuta las pruebas directas **antes** de levantar el
> backend para los E2E. Con `QDRANT_MODE=server` esta limitación desaparece.

### Colecciones

| Colección | Contenido | ACL |
|---|---|---|
| `matrix_rh_corporate` | Conocimiento corporativo | filtro por `scope=corporate` + `category IN (...)` |
| `matrix_rh_private` | Adjuntos de conversación | filtro por `scope=conversation` + `owner_user_id` + `conversation_id` |

---

## 3. Metadata de cada chunk

Definida en `backend/app/rag/schemas.py::ChunkMetadata`:

`chunk_id`, `document_id`, `document_sha256`, `filename`, `relative_path`,
`category`, `subpath`, `mime_type`, `page_or_sheet`, `section`, `chunk_index`,
`text`, `embedding_model`, `embedding_dimension`, `ingestion_version`,
`allowed_roles`, `allowed_groups`, `sensitivity`, `scope`, `owner_user_id`,
`conversation_id`, `created_at`, `updated_at`.

El `source_id` citable se compone como `categoria/archivo#indice`.

---

## 4. Filtros de autorización

`VectorStore.build_corporate_filter(categorias_autorizadas)` construye siempre
una lista **enumerada** de categorías. Incluso el rol administrativo con wildcard
llega aquí con su lista ya resuelta por `PolicyEngine.effective_categories`:
**nunca se consulta sin filtro**.

Si el usuario no tiene ninguna categoría autorizada, el filtro usa una condición
imposible (`category = "__none__"`) en lugar de omitirse. Omitir un filtro vacío
es el error clásico que convierte una restricción en acceso total.

---

## 5. Pipeline de ingesta

```
discover -> authorize policy metadata -> extract -> normalize
   -> structural split -> chunk -> embed -> upsert -> manifest -> verify
```

Implementado en `backend/app/ingestion/service.py::IngestionService._index_document`.

**Orden crítico**: al reindexar se **borran primero** los vectores del documento
y después se insertan los nuevos. Al revés quedarían chunks huérfanos de una
versión anterior mezclados con los actuales.

### Manifest

El manifest es la propia base interna:

- `documents` — estado actual: SHA-256, número de chunks, estado, versión del pipeline.
- `document_versions` — histórico de reindexados.

Se eligió la base de datos frente a un JSON en disco porque la reconciliación
necesita consultas por SHA y por ruta, y un archivo suelto se desincroniza en
cuanto dos procesos escriben a la vez.

---

## 6. Extracción por formato

| Formato | Estrategia | Límites |
|---|---|---|
| `.docx` | Conserva títulos (nivel de heading), subtítulos, listas, tablas y orden. Las tablas se serializan en Markdown. | — |
| `.md` | Preserva headings, listas y bloques semánticos. | 20 MB |
| `.pdf` | Texto por página. Una página sin capa de texto genera un **aviso explícito**; no se inventa contenido. | 500 páginas |
| `.txt` | Detección de encoding (`utf-8-sig`, `utf-8`, `cp1252`, `latin-1`) con fallback tolerante. | 20 MB |
| `.xlsx` | Por hoja: conserva el nombre de la hoja y los encabezados; cada fila se serializa como `columna: valor`. | 50 hojas, 5000 filas/hoja, 100 columnas |
| `.csv` | Detección de delimitador + mismo formato `columna: valor`. | 20 000 filas |

**No se ejecutan macros, fórmulas ni contenido incrustado.** `openpyxl` se abre
con `data_only=True`, que lee el valor cacheado y nunca evalúa la fórmula
(verificado en `tests/unit/test_loaders.py::TestXlsx::test_no_evalua_formulas`).

### Limitación de PDF sin texto

Un PDF escaneado sin OCR produce `warnings` del tipo
`"Paginas sin texto extraible (posible escaneo sin OCR): 1, 2, 3"` y el documento
queda en estado `empty`. Matrix RH prefiere declarar que no puede leer una página
antes que fabricar una política.

---

## 7. Chunking

Prioridad de separadores:

1. **Encabezados / secciones** — frontera dura.
2. Párrafos.
3. Listas (agrupadas como un bloque).
4. Tablas / filas (agrupadas como un bloque).
5. Fallback por tokens (frases, luego palabras).

Un encabezado **abre chunk nuevo** aunque el actual no esté lleno, siempre que se
hayan acumulado al menos `HEADING_BREAK_MIN_TOKENS` (80). Esta regla se añadió
tras medir el corpus real: sin ella, un documento de política de 600 tokens caía
en **un único chunk** y su embedding quedaba diluido entre temas distintos. Con
la regla, el mismo corpus pasó de 6 a 24 chunks y la similitud de la mejor
coincidencia subió de ~0.29 a 0.40-0.72.

Una lista corta o un procedimiento breve **no se parten** si caben dentro del
tamaño máximo.

### Estimación de tokens

Se usa una aproximación determinista (`palabras × 1.3`) en lugar del tokenizador
del modelo, que Ollama no expone por API. Una estimación estable y reproducible
es preferible a una exacta pero dependiente del modelo; los valores por defecto
(900/120) dejan margen de sobra para el error.

---

## 8. Prefijos de tarea de embeddinggemma

`embeddinggemma` es un modelo instruido: espera prefijos distintos para consulta
y documento (`backend/app/rag/embedding_prompts.py`).

| Uso | Plantilla |
|---|---|
| Consulta | `task: search result \| query: {texto}` |
| Documento | `title: {sección o archivo} \| text: {texto}` |

Sin estos prefijos, consulta y documento caen en regiones distintas del espacio
vectorial. Síntoma medido durante la construcción: la pregunta *"con qué
frecuencia se realizan los simulacros"* no recuperaba el párrafo que dice
literalmente *"los simulacros se realizan de forma trimestral"*.

Los prefijos forman parte del contrato de indexación: cambiarlos obliga a
reindexar, por eso van acompañados de `INGESTION_VERSION`.

---

## 9. Recuperación

Orden implementado en `backend/app/rag/retriever.py::Retriever.retrieve`:

1. Resolver identidad y permisos (ya vienen en el `UserContext` firmado).
2. Determinar categorías autorizadas (`PolicyEngine.effective_categories`).
3. Crear la consulta semántica (embedding con prefijo de query).
4. Recuperar `fetch_k` en Qdrant **con el filtro de permisos y `score_threshold`**.
5. Eliminar duplicados y chunks casi equivalentes (`deduplicate`).
6. Aplicar MMR (`maximal_marginal_relevance`).
7. Devolver como máximo `top_k`.
8. Preservar diversidad por categoría cuando la pregunta es comparativa
   (`enforce_category_diversity`).
9. Entregar scores y `source_id` al Agente de Conocimiento.

La reformulación de la consulta **nunca** es evidencia.

---

## 10. Resumen de adjuntos por metadata

`Retriever.retrieve_attachment_summary` usa una ruta distinta de la búsqueda
semántica. Una petición como «Resume esto» no describe el contenido, así que un
embedding de esa frase podría quedar bajo el umbral aun cuando el archivo esté
correctamente indexado.

`VectorStore.list_private_chunks` pagina mediante `scroll` y aplica dentro de
Qdrant las tres condiciones obligatorias:

```text
scope = conversation
owner_user_id = usuario autenticado
conversation_id = conversación actual
```

No se genera embedding, no se usa `score_threshold` y no se consulta el corpus
corporativo en esta primera etapa. El límite de scan es 256 chunks; se pide uno
adicional para saber si hubo truncamiento y comunicarlo.

Los chunks se ordenan por archivo e índice. Si el material cabe en el contexto
del modelo elegido, se resume en una llamada. Si no, se particiona en lotes de
hasta 24 chunks: Gemma procesa como máximo dos lotes en paralelo y Qwen integra
los resúmenes parciales conservando citas. El reduce, los parciales y el fallback
extractivo pasan por verificación de `source_id`.

Si la conversación no tiene evidencia privada, una solicitud de resumen puede
continuar con búsqueda corporativa autorizada para casos como «resume la política
de vacaciones». No mezcla adjuntos de otra conversación o usuario.

---

## 11. Grounding

El prompt separa cuatro bloques que no se mezclan
(`backend/app/agents/prompts.py`):

| Bloque | Delimitador | Papel |
|---|---|---|
| Pregunta del usuario | `PREGUNTA DEL USUARIO:` | lo que se responde |
| Memoria conversacional | `<<<MEMORIA_CONVERSACION>>>` | contexto de diálogo, **no** evidencia factual |
| Evidencia documental | `<<<EVIDENCIA_DOCUMENTAL>>>` | única base factual documental |
| Resultados estructurados | `<<<RESULTADOS_ESTRUCTURADOS>>>` | única base factual de datos |

`verify_grounding` (en `backend/app/rag/grounding.py`) rechaza la síntesis si el
modelo cita un `source_id` que no fue recuperado. Política anti-loop: **una** sola
regeneración; si insiste en citar fuentes inexistentes se responde insuficiencia.

---

## 12. Actualización cada 24 horas

`backend/app/jobs/scheduler.py` lanza `reconcile_with_lock` cada
`RAG_REINDEX_INTERVAL_HOURS`. La reconciliación
(`backend/app/ingestion/reconciler.py`):

1. recorre recursivamente el knowledge root;
2. detecta carpetas nuevas → nuevas categorías con deny-by-default;
3. detecta archivos nuevos;
4. detecta archivos modificados **por SHA-256** (no por fecha: copiar un archivo
   cambia la fecha sin cambiar el contenido);
5. detecta archivos eliminados;
6. reindexa sólo lo necesario;
7. elimina los chunks obsoletos;
8. no duplica documentos ni chunks;
9. actualiza el manifest;
10. registra resultados y errores en `ingestion_jobs`.

El job es idempotente y usa un lock cooperativo en `job_locks` con expiración,
que también cubre el caso de dos procesos distintos.

Los `README.md` de las carpetas de conocimiento se excluyen de la ingesta: son
documentación del repositorio, no conocimiento corporativo.

---

## 13. Evaluación del RAG

Golden set sintético en `backend/tests/rag_eval/golden_set.yaml` (36 casos):
prestaciones, nómina, reclutamiento, relaciones laborales, salud ambiental,
comparativas, preguntas sin respaldo y preguntas restringidas.

Métricas producidas por `backend/scripts/rag_eval.py`:

- `retrieval_hit_rate` — la evidencia incluye la categoría esperada.
- `source_correctness` — toda la evidencia proviene de categorías autorizadas.
- `grounded_answer_rate` — respuestas verificadas como fundamentadas (modo `--full`).
- `unsupported_claim_rate` — casos sin respaldo en los que el sistema afirmó algo.
- `acl_leakage_rate` — **debe ser 0**.

Criterios de aprobación: **≥98 %** de casos y **0** fugas ACL.

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.rag_eval --retrieval
```
```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.rag_eval --full --output reports\tests\rag_eval.json
```
