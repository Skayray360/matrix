<!-- Creado por Aldo Garcia. -->

# app/llm/

Capa de modelos locales.

| Archivo | Contenido |
|---|---|
| `ollama_client.py` | Cliente único hacia Ollama |
| `model_policy.py` | Clasificación de intención y router de modelos |

## Cliente único

Ningún otro módulo abre conexiones HTTP hacia Ollama. Un solo punto para
timeouts, reintentos, keep-alive, métricas y preflight.

Los reintentos se limitan a errores **transitorios** (timeout, red, 5xx). Un 4xx
no se reintenta: indica una petición incorrecta y reintentarla sólo esconde el
diagnóstico.

El cliente envía `keep_alive=15m`, reutiliza conexiones HTTP (20 totales, 10 en
keep-alive, conexión acotada a 10 s) y mantiene un LRU de 256 embeddings. La
clave de caché es modelo + SHA-256; no conserva la pregunta en texto.

## Verificación de dimensión

`embed()` comprueba la longitud real de **cada** vector. Si no coincide con la
configurada, lanza `EmbeddingDimensionMismatchError`. **Nunca se trunca ni se
rellena.**

## Modelos

`gemma4:latest` (rápido), `qwen3.6:latest` (profundo), `embeddinggemma:latest`
(embeddings). No se sustituyen por modelos cloud; hay una prueba que lo verifica.

| Perfil | `num_ctx` | `num_predict` | Uso |
|---|---:|---:|---|
| Gemma | 8 192 | 768 | ruta normal y mapas de resumen |
| Qwen | 32 768 | 2 048 | análisis/comparativas y reduce de resumen largo |

Gemma es el modelo predeterminado. Qwen se activa sólo por señales deterministas
del router: profundidad explícita, longitud, varias preguntas/categorías, flujo
multiherramienta, baja confianza, intención mixta o resumen grande. Si un modelo
recibe un error HTTP específico, se intenta una vez el otro modelo local; no se
duplica un error de transporte ni se usa nube.

Las intenciones `identity`, `document_summary`, `documental`, `structured`,
`mixed`, `conversational` y `general` mantienen separadas la identidad, la
capacidad general y los turnos documentales. El contrato completo está en
[`../../../docs/AI_DESIGN.md`](../../../docs/AI_DESIGN.md).
