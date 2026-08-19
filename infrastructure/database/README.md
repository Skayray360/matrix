<!-- Creado por Aldo Garcia. -->

# infrastructure/database/

Inicialización de la base interna.

`init/01-create-database.sql` crea la base con `utf8mb4` y un usuario de
aplicación con permisos mínimos.

## Recomendaciones

- **No usar `root`** fuera de un equipo de desarrollo local.
- Conceder únicamente `SELECT, INSERT, UPDATE, DELETE` sobre la base de Matrix RH.
- Las migraciones necesitan `CREATE`/`ALTER`: puede usarse un usuario de despliegue
  distinto del usuario de runtime.
- Programar `mysqldump` de la base interna. El índice vectorial no lo necesita.
