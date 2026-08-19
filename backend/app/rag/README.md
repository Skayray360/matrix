<!-- Creado por Aldo Garcia. -->

# app/rag/

RAG custom: chunking, vector store con ACL, recuperación y grounding.

| Archivo | Contenido |
|---|---|
| `schemas.py` | `Chunk`, `ChunkMetadata`, `Evidence` |
| `chunking.py` | Bloques estructurales y chunking con frontera por encabezado |
| `embedding_prompts.py` | Prefijos de tarea de `embeddinggemma` |
| `vector_store.py` | Qdrant con filtros ACL en la consulta |
| `retriever.py` | búsqueda semántica y recuperación privada de resumen por metadata |
| `grounding.py` | Verificación de citas y allowlist de fuentes |

## Lo importante

- El filtro de autorización **forma parte de la consulta** a Qdrant. Los chunks
  restringidos no entran ni en `fetch_k`.
- Un usuario sin categorías autorizadas recibe un filtro imposible, no un filtro
  ausente.
- Una cita que no corresponde a evidencia recuperada invalida la respuesta.
- «Resume el archivo» no usa similitud: hace scroll privado con filtro obligatorio
  `scope + owner_user_id + conversation_id`, hasta 256 chunks.
- Si el scan se trunca, la respuesta debe indicarlo; los lotes de síntesis se
  acotan a 24 chunks.

Parámetros y su justificación:
[`../../../docs/RAG_DESIGN.md`](../../../docs/RAG_DESIGN.md).
