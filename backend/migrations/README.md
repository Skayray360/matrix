<!-- Creado por Aldo Garcia. -->

# backend/migrations/

Migraciones SQL versionadas.

| Archivo | Contenido |
|---|---|
| `0001_initial_schema.sql` | Esquema completo |
| `0002_widen_audit_status.sql` | Amplía columnas de estado de auditoría e ingesta |
| `0003_message_sequence.sql` | Secuencia estable de mensajes dentro de cada conversación |

## Convenciones

- Nombre `NNNN_descripcion.sql`, cuatro dígitos, orden estricto.
- Todas las sentencias idempotentes (`IF NOT EXISTS`, `ALTER` seguros).
- Una migración aplicada **no se edita**: se crea una nueva. El runner verifica
  el checksum y falla si cambió.
- Claves primarias `CHAR(36)` (UUID4), InnoDB, `utf8mb4_unicode_ci`.
- `trigger` es palabra reservada en MySQL: la columna se llama `trigger_source`.

## Aplicar

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap migrate
```
