<!-- Creado por Aldo Garcia. -->

# backend/seeds/

Semillas reproducibles.

`identity_seed.py` crea roles, permisos, políticas de categoría y las dos cuentas
sintéticas:

| Usuario | Rol | Acceso |
|---|---|---|
| `Matrix` | `matrix_admin_test` | Wildcard de categorías de negocio |
| `MatrixR1` | `prestaciones_reader_test` | Sólo `prestaciones` |

## Advertencia

Son **credenciales sintéticas conocidas de prueba**, no secretos productivos. La
contraseña nunca se almacena en claro: sólo un hash Argon2id. El seed está
**prohibido** con `APP_ENV=production` y el arranque falla si sigue habilitado.

## Idempotencia

Reejecutarlo no duplica usuarios, roles ni concesiones.

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap seed
```
