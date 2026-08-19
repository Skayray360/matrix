<!-- Creado por Aldo Garcia. -->

# app/api/

Capa HTTP: gateway único del frontend hacia Matrix RH.

| Archivo | Contenido |
|---|---|
| `deps.py` | Sesión de BD, `UserContext`, CSRF, permisos |
| `middleware.py` | Request id, cabeceras de seguridad, manejo de errores |
| `schemas.py` | Modelos Pydantic de request/response con límites explícitos |
| `routes/health.py` | `/health` y `/ready` con semántica distinta |
| `routes/auth.py` | Login Entra/local, logout, `/me` |
| `routes/chat.py` | Turno de conversación |
| `routes/conversations.py` | Conversaciones, adjuntos, estado de documentos |
| `routes/admin.py` | Conocimiento corporativo, auditoría propia, diagnóstico |

## Reglas

- `get_user_context` es el punto por el que pasa toda ruta autenticada.
- Ninguna ruta acepta `user_id`, `role` o `groups` del cliente.
- Todo método mutante exige `X-CSRF-Token` válido para esa sesión.
- Los errores devuelven sólo `code`, `message` y `request_id`.
- Las cabeceras de seguridad se aplican desde el backend, no sólo desde el proxy:
  el arranque por doble clic no lleva proxy delante.
