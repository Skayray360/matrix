<!-- Creado por Aldo Garcia. -->

# infrastructure/database/init/

Inicialización mínima de la base interna cuando se usa la topología de
contenedores.

- Entrada: variables de entorno de MySQL definidas por el despliegue.
- Proceso: `01-create-database.sql` crea la base y la cuenta limitada necesarias.
- Salida: esquema vacío preparado para que Alembic aplique las migraciones.
- Dependencia: una imagen MySQL/MariaDB compatible y credenciales de arranque
  entregadas fuera del repositorio.

Este directorio no sustituye las migraciones ni el bootstrap de Windows. No
agregue datos funcionales, secretos ni usuarios nominales a los SQL de inicio.
