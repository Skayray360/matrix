<!-- Creado por Aldo Garcia. -->

# app/database/

Persistencia interna sobre MySQL/MariaDB con SQLAlchemy 2.

| Archivo | Contenido |
|---|---|
| `engine.py` | Engine perezoso con `pool_pre_ping`, `session_scope()` |
| `models.py` | Modelos ORM, reflejo exacto del DDL de `migrations/` |
| `migrator.py` | Runner idempotente de migraciones |

## Por qué un runner propio y no Alembic

El instalador Windows debe aplicar el esquema en frío, varias veces seguidas, sin
estado previo y sin dependencias adicionales. Cada archivo
`NNNN_nombre.sql` se aplica una sola vez y queda registrado con su **checksum**.
Si una migración ya aplicada cambia de contenido, el runner falla en lugar de
reaplicarla.

## Protección contra bases ajenas

`assert_database_is_ours` aborta si la base configurada ya contiene tablas de
otra aplicación. Es una protección real: durante la construcción el equipo
destino tenía una base `matrix_rh` de otro proyecto.

## Sincronización ORM ↔ DDL

`tests/integration/test_schema_and_seed.py::test_el_esquema_real_coincide_con_los_modelos_orm`
compara los modelos con `information_schema` para impedir que se desincronicen.
