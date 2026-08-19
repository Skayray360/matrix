# Diseño de IA — Matrix RH

> Creado por Aldo Garcia.

Matrix RH usa dos LLM locales con rutas deterministas. La capacidad general de
los modelos está disponible, pero nunca se mezcla con políticas, documentos o
datos internos: esos turnos siguen siendo *document-grounded* y con ACL.

## 1. Agentes y fronteras

| Componente | Responsabilidad | Frontera |
|---|---|---|
| Orquestador | Clasificar intención, autorizar, elegir herramienta/modelo, auditar | No sintetiza desde fuentes sin pasar por su tool |
| Tool RAG | Recuperar corporativo con categorías o adjuntos con ownership | No amplía categorías ni devuelve texto fuera del filtro Qdrant |
| Tool estructurada | Ejecutar un plan validado sobre fuentes concedidas | No acepta SQL libre |
| Agente de Conocimiento | Sintetizar y verificar citas sobre evidencia recibida | No conoce el vector store ni el motor de políticas |

La autorización ocurre antes de recuperar o construir el prompt. El texto de un
documento se trata como dato no confiable, nunca como instrucción.

## 2. Intenciones y contrato de identidad

La clasificación vive en `backend/app/llm/model_policy.py`, no en un LLM. Es
normalizada, determinista y no consume inferencia.

| Intención | Detección | Ejecución |
|---|---|---|
| `identity` | «quién eres», «cómo te llamas», «identifícate», equivalentes | Respuesta exacta `Soy Matrix RH.` sin RAG ni LLM |
| `document_summary` | «resume», «resumen», «sintetiza», «puntos clave», «ideas principales» | Adjuntos privados por metadata; si no hay adjunto, RAG corporativo autorizado |
| `documental` | Referencia a documento/fuente o vocabulario de RH: política, nómina, vacaciones, salario, etc. | RAG con ACL; sin evidencia se declara insuficiencia |
| `structured` | Marcadores de conteo o agregación sobre personas/datos | Plan estructurado validado y fuente concedida |
| `mixed` | Señales documentales y estructuradas | Ambas tools; evidencia separada |
| `conversational` | Saludos/despedidas cortos | Ruta general sin fuentes internas |
| `general` | Solicitud fuera de RH y sin referencia documental | Conocimiento general del modelo, sin citas corporativas |

El orden evita dos errores: una pregunta general ya no recibe falsamente el
mensaje de insuficiencia documental, y una consulta de RH no puede aprovechar
conocimiento general para inventar una regla interna. La ruta general tiene un
*system policy* separado que prohíbe presentar su respuesta como dato de la
empresa.

## 3. Política de los dos modelos

### Ruta rápida — `gemma4:latest`

Es la selección predeterminada para conversación, conocimiento general,
preguntas documentales normales y resúmenes cortos. Su presupuesto busca menor
latencia sin sacrificar una respuesta sustantiva:

| Parámetro | Valor predeterminado |
|---|---:|
| `OLLAMA_FAST_NUM_CTX` | 8 192 |
| `OLLAMA_FAST_MAX_TOKENS` | 768 |

### Ruta profunda — `qwen3.6:latest`

Se usa cuando al menos una señal justifica razonamiento o contexto adicional:

| Señal auditable | Condición |
|---|---|
| `deep_marker_in_query` | comparación, análisis profundo, contradicciones, implicaciones, etc. |
| `long_query` | consulta de 320 caracteres o más |
| `multiple_questions` | más de dos signos `?` |
| `multi_category_comparison` | evidencia de dos o más categorías |
| `multi_tool_flow` | RAG y datos estructurados en el mismo turno |
| `low_retrieval_confidence` | mejor score menor que `RAG_MIN_SIMILARITY + 0.05` |
| `verifier_requested_deep` | el verificador solicita cobertura adicional |
| `mixed_intent` | intención mixta |
| `large_document_summary` | resumen con más de 4 chunks o más de 10 000 caracteres de evidencia |

| Parámetro | Valor predeterminado |
|---|---:|
| `OLLAMA_DEEP_NUM_CTX` | 32 768 |
| `OLLAMA_DEEP_MAX_TOKENS` | 2 048 |

La temperatura depende de la tarea: `0.25` para general/conversacional, `0.08`
para resumen, `0.10` para documental/estructurada y `0.03` en regeneración. Los
presupuestos son límites de inferencia, no promesas de calidad ni de tiempo.

## 4. Resumen de adjuntos

Un resumen no es una búsqueda semántica. «Resume esto» puede no compartir ninguna
palabra con el archivo, por lo que Matrix RH no genera embedding ni aplica
`RAG_MIN_SIMILARITY` en esta ruta.

1. Qdrant hace `scroll` sobre la colección privada.
2. El filtro `MUST` contiene `scope=conversation`, `owner_user_id` y
   `conversation_id`.
3. Los chunks se ordenan por archivo e índice y se deduplican.
4. Se escanean como máximo `RAG_SUMMARY_SCAN_MAX_CHUNKS=256`.
5. Si la evidencia cabe en el contexto elegido, se hace una síntesis con citas.
6. Si no cabe, se divide en lotes de hasta
   `RAG_SUMMARY_MAX_CHUNKS=24`: Gemma procesa hasta dos lotes en paralelo y Qwen
   integra los parciales.
7. Todas las citas finales se verifican contra los `source_id` recuperados.

Si existen chunks legibles pero el modelo declara insuficiencia, se permite una
regeneración. Si vuelve a hacerlo o no conserva citas válidas, se entrega un
resumen extractivo citado; nunca se transforma evidencia real en un falso vacío.
Si había más de 256 chunks, la respuesta indica explícitamente que se procesó
material hasta ese límite.

Esta ruta no permite elegir un archivo concreto cuando hay varios adjuntos: el
alcance técnico es la conversación completa. Para aislar un documento, utilice
una conversación nueva.

## 5. Grounding y regeneración

| Riesgo | Control |
|---|---|
| Documento sin evidencia | no se llama al modelo; respuesta de insuficiencia |
| Fuente inventada | `verify_grounding` compara cada cita con una allowlist literal |
| Cobertura pobre con evidencia rica | una regeneración, potencialmente con Qwen |
| Memoria usada como hecho | bloque separado, marcado como no factual |
| Prompt injection documental | delimitadores + política + ausencia de herramientas privilegiadas |
| Fuga entre adjuntos | ownership en el filtro Qdrant, no posfiltrado |
| Resumen largo pierde secciones | map/reduce con verificación; fallback a parciales o extractivo |

Sólo hay una regeneración de calidad. Independientemente, si Ollama responde con
un error HTTP específico del modelo, se prueba una sola vez el otro modelo local.
Un error de transporte no se duplica porque afectaría al mismo servidor. Nunca se
introduce un proveedor cloud.

## 6. Rendimiento local

- `OLLAMA_KEEP_ALIVE=15m` reduce recargas del modelo entre turnos.
- El cliente HTTP reutiliza hasta 20 conexiones, 10 en *keep-alive*, con timeout
  de conexión acotado a 10 s.
- Las consultas repetidas reutilizan un LRU de 256 embeddings, identificado por
  modelo + SHA-256; la clave no guarda el texto.
- Gemma atiende la ruta normal; Qwen sólo se carga cuando una señal aporta valor.
- El resumen largo paraleliza como máximo dos mapas para no saturar el equipo.

La latencia real depende de RAM, VRAM, reparto CPU/GPU, tamaño de contexto y
estado de carga. `ollama ps` muestra dónde está ejecutándose cada modelo; los
eventos `chat.answer` conservan modelo y `latency_ms`.

## 7. Control de contexto

| Elemento | Límite predeterminado |
|---|---:|
| Mensaje del usuario | 8 000 caracteres |
| Evidencia documental normal por chunk | 2 200 caracteres |
| Evidencia de resumen por chunk | 2 600 caracteres |
| Turnos recientes | 6 configurables |
| Texto por turno reenviado | 1 200 caracteres |
| Filas estructuradas en prompt | 25 |
| Scan privado para resumen | 256 chunks |
| Lote de resumen | 24 chunks |

El resumen interno de una conversación es sólo continuidad de diálogo. Omite
cifras, políticas, documentos y citas para que no sobrevivan hechos a un cambio
de permisos.

## 8. Evaluación y límites

Los controles de routing, identidad, separación general/documental, ACL privada,
resumen, fallback y parámetros tienen pruebas unitarias. El RAG corporativo usa
un golden set sintético y el gate crítico sigue siendo **0 % de fuga ACL**.

Límites deliberados:

- no hay streaming: las citas se verifican antes de mostrar la respuesta;
- un PDF sin texto no recibe OCR implícito;
- conocimiento general no es fuente corporativa y no produce citas internas;
- el resumen privado cubre la conversación, no un selector de archivo;
- Qwen puede tardar varios minutos si Ollama lo ejecuta parcialmente en CPU.

Parámetros RAG y ubicación exacta en código:
[`RAG_DESIGN.md`](RAG_DESIGN.md).
