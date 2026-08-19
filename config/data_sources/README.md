<!-- Creado por Aldo Garcia. -->

# config/data_sources/

`sources.yaml` — catálogo de fuentes estructuradas.

## Regla que no se rompe

**No contiene DSN ni credenciales.** `secret_ref` es el *nombre* de la variable
de entorno que contiene la cadena de conexión de una cuenta **read-only**.

Si la variable no existe, la fuente queda `PREPARED_NOT_CONNECTED` y el sistema
lo declara honestamente en lugar de simular una conexión.

## Qué define cada fuente

Nombre lógico, motor, `secret_ref`, timeout, máximo de filas, roles autorizados y
la lista de entidades con sus columnas permitidas y filtros organizacionales
obligatorios.

Una columna que no esté en `allowed_columns` **no puede** proyectarse, filtrarse,
agruparse ni ordenarse. Ver `docs/integrations/DATABASE_CONNECTORS.md`.
