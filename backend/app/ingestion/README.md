<!-- Creado por Aldo Garcia. -->

# app/ingestion/

Ingesta de conocimiento corporativo y de adjuntos privados.

| Archivo | Contenido |
|---|---|
| `loaders.py` | Extractores por formato con límites anti-abuso |
| `service.py` | Pipeline extract → chunk → embed → upsert → manifest |
| `reconciler.py` | Reconciliación incremental por SHA-256 con lock |

El corpus permanente sigue el contrato descrito en
[`data/knowledge/README.md`](../../../data/knowledge/README.md): documentación
`general` para el perfil base y dominios `especializadas` con ACL propia. Los
adjuntos de chat nunca se escriben en ese árbol; viven en un namespace privado
`user_id + conversation_id`.

## Idempotencia

Si el SHA-256 no cambió, no se reindexa. Si cambió, se **borran primero** los
vectores del documento y luego se insertan los nuevos: al revés quedarían chunks
huérfanos de una versión anterior mezclados con los actuales.

## Manifest

Es la propia base interna (`documents` + `document_versions`), no un JSON en
disco: la reconciliación necesita consultas por SHA y por ruta, y un archivo
suelto se desincroniza en cuanto dos procesos escriben a la vez.

## Seguridad de la extracción

Sin macros, sin fórmulas, sin contenido incrustado. Límites de páginas, hojas,
filas, celdas y ratio de descompresión. Un PDF sin capa de texto genera un aviso
explícito; **no se inventa contenido**.

Un archivo listo para consultar o resumir debe tener estado `indexed`. `empty`
significa que no produjo texto utilizable; `failed` conserva un mensaje seguro
para diagnóstico.
