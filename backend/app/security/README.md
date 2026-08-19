<!-- Creado por Aldo Garcia. -->

# app/security/

Controles de seguridad transversales.

| Archivo | Contenido |
|---|---|
| `upload_guard.py` | Allowlist, magic bytes, límites, anti-zip-bomb, rutas seguras |
| `rate_limit.py` | Ventana deslizante en memoria |
| `prompt_guard.py` | Neutralización de marcadores y detección de inyección |

## Sobre el prompt guard

No intenta "detectar todas las inyecciones" —eso no es alcanzable—. Reduce la
superficie: delimita la evidencia, neutraliza secuencias que imitan marcadores de
rol y registra patrones imperativos.

La defensa real es arquitectónica: el modelo no tiene herramientas capaces de
ampliar permisos y el filtro ACL se aplicó antes de construir el prompt.

Un mensaje sospechoso **no se bloquea**: bloquearlo revelaría que ciertas
palabras disparan el sistema.
