# Conectores de bases de datos externas — Matrix RH

> Creado por Aldo Garcia.

Matrix RH consulta fuentes estructuradas **sólo en lectura** y **sólo mediante un
plan JSON validado**. El LLM nunca envía SQL.

---

## 1. Modelo de conexión

```mermaid
flowchart LR
    P[StructuredQueryPlan JSON] --> V[QueryPolicyValidator]
    V --> C[Compilador parametrizado]
    C --> A[Verificacion AST sqlglot]
    A --> AD[ReadOnlySourceAdapter]
    AD --> DB[(Motor externo, cuenta read-only)]
```

Cada fuente se declara en `config/data_sources/sources.yaml`. Ese archivo **no
contiene credenciales**: `secret_ref` es el *nombre* de la variable de entorno
que contiene el DSN.

---

## 2. Estructura de una fuente

```yaml
- name: rh_demo                  # identificador seguro [A-Za-z_][A-Za-z0-9_]*
  engine: mysql                  # mysql | mariadb | postgresql | sqlserver | oracle | sqlite
  description: Fuente sintetica de demostracion.
  enabled: false                 # false => PREPARED_NOT_CONNECTED
  secret_ref: MATRIX_DEMO_DB_DSN # NOMBRE de la variable, nunca el DSN
  timeout_seconds: 15
  max_rows: 200
  allowed_roles: [hcm_adm_ia_matrix]
  entities:
    - name: plantilla            # nombre lógico expuesto al planificador
      table: demo_plantilla      # tabla o VISTA de seguridad real
      allowed_columns: [empleado_id, departamento, centro_trabajo, puesto, antiguedad_anios, estatus]
      required_filters:          # se añaden SIEMPRE a la consulta
        estatus: activo
      max_rows: 200
```

Reglas que aplica el validador:

- La fuente debe existir y estar `enabled`.
- El rol del usuario debe tenerla concedida en `structured_source_permissions`.
- La entidad debe estar declarada.
- **Todas** las columnas referenciadas (proyección, filtro, agrupación, orden,
  agregación) deben estar en `allowed_columns`.
- El límite efectivo es el menor entre el del plan, el de la entidad y el de la
  fuente.
- Los `required_filters` se **añaden**, nunca se sustituyen por los del plan.

### Concesiones corporativas iniciales

| Rol HCM | `structured.query` | Fuentes en `StructuredSourcePermission` |
|---|---|---|
| `hcm_adm_ia_matrix` | sí | `rh_demo`, `postgres_analytics` |
| `hcm_adm_admpersonal` | sí | `sap_hcm`, `oracle_hcm` |
| cualquier `hcm_coord_*` | no | ninguna |
| otros `hcm_adm_*` | no | ninguna |

`matrix_admin_test` conserva acceso a las cuatro fuentes para pruebas locales;
no es un rol corporativo y está prohibido en producción.

---

## 3. Pasos por motor

### MySQL / MariaDB

| Paso | Detalle |
|---|---|
| Driver | `mysql+pymysql` (incluido) |
| DSN | `mysql+pymysql://usuario:clave@host:3306/base?charset=utf8mb4` |
| Usuario read-only | `CREATE USER 'matrixrh_ro'@'%' IDENTIFIED BY '<clave>';`<br>`GRANT SELECT ON base.vw_matrixrh_* TO 'matrixrh_ro'@'%';` |
| TLS | Añadir `?ssl_ca=/ruta/ca.pem` al DSN |
| Query de prueba | `SELECT 1` |
| Variable | `MATRIX_DEMO_DB_DSN` |

### PostgreSQL

| Paso | Detalle |
|---|---|
| Driver | `postgresql+psycopg` — extra bloqueado `postgres` (ver §4) |
| DSN | `postgresql+psycopg://usuario:clave@host:5432/base` |
| Usuario read-only | `CREATE ROLE matrixrh_ro LOGIN PASSWORD '<clave>';`<br>`GRANT USAGE ON SCHEMA rh TO matrixrh_ro;`<br>`GRANT SELECT ON rh.vw_rotacion_mensual TO matrixrh_ro;` |
| TLS | `?sslmode=require` |
| Query de prueba | `SELECT 1` |
| Variable | `MATRIX_PG_ANALYTICS_DSN` |

### SQL Server

| Paso | Detalle |
|---|---|
| Driver | `mssql+pymssql` — extra bloqueado `mssql` (ver §4) |
| DSN | `mssql+pymssql://usuario:clave@host:1433/base` |
| Usuario read-only | `CREATE LOGIN matrixrh_ro WITH PASSWORD = '<clave>';`<br>`CREATE USER matrixrh_ro FOR LOGIN matrixrh_ro;`<br>`GRANT SELECT ON dbo.vw_matrixrh_empleado_resumen TO matrixrh_ro;` |
| TLS | `?encrypt=true` según la configuración del servidor |
| Query de prueba | `SELECT 1` |
| Variable | `MATRIX_SAP_HCM_DSN` |
| Nota | El compilador usa `SELECT TOP n` en este dialecto |

### Oracle

| Paso | Detalle |
|---|---|
| Driver | `oracle+oracledb` — extra bloqueado `oracle` (ver §4) |
| DSN | `oracle+oracledb://usuario:clave@host:1521/?service_name=SERVICIO` |
| Usuario read-only | `CREATE USER MATRIXRH_RO IDENTIFIED BY "<clave>";`<br>`GRANT CREATE SESSION TO MATRIXRH_RO;`<br>`GRANT SELECT ON RH.VW_MATRIXRH_POSICIONES TO MATRIXRH_RO;` |
| TLS | Configurar wallet / `TCPS` en el DSN |
| Query de prueba | `SELECT 1 FROM DUAL` |
| Variable | `MATRIX_ORACLE_HCM_DSN` |
| Nota | El compilador usa `FETCH FIRST n ROWS ONLY` |

---

## 4. Habilitar una fuente

1. Definir la variable de entorno con el DSN read-only (fuera del repositorio).
2. Instalar el extra bloqueado del driver desde la raíz; por ejemplo, SQL
   Server:

   ```bat
   cd backend
   set "UV_PROJECT_ENVIRONMENT=%CD%\..\.venv"
   uv sync --frozen --extra mssql
   cd ..
   ```

   Use `postgres` u `oracle` en lugar de `mssql` para esos motores.
3. Poner `enabled: true` en `sources.yaml`.
4. Añadir el rol a `allowed_roles` y confirmar `structured.query` en
   `entra-role-mapping.yaml`. No edite la tabla a mano.
5. Ejecutar el dry-run y luego reconciliar:

   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.load_entra_mapping --dry-run
   .venv\Scripts\python.exe -m scripts.load_entra_mapping --prune
   ```

6. Reiniciar el backend y probar un rol permitido y otro denegado.

---

## 5. Cómo validar `/ready`

```bash
curl http://127.0.0.1:8000/ready
```

Y el estado detallado de cada fuente:

```bash
curl http://127.0.0.1:8000/api/v1/admin/diagnostics
```

`structured_sources` debe mostrar `CONNECTED_AND_VALIDATED` para las habilitadas.
Si aparece `PREPARED_NOT_CONNECTED`, falta el DSN. Si aparece `ERROR`, el DSN
existe pero la conexión falla.

Con `MATRIX_EXTERNAL_CONNECTORS_REQUIRED=true`, una fuente en `ERROR` hace fallar
el preflight; con `false` (por defecto) sólo genera un aviso.

---

## 6. Test de contrato

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m pytest backend\tests\unit\test_structured_query.py -q
```

Cubre: esquema del plan, rechazo de campos inventados, identificadores inseguros,
columnas no autorizadas, entidad y fuente desconocidas, denegación por rol,
inyección de filtros obligatorios, acotado de límites, parametrización de valores,
`IN` vacío y verificación por AST (DDL, DML, múltiples sentencias, comentarios,
`UNION`, subconsultas y tablas no autorizadas).

Para validar una fuente **real** una vez conectada:

```python
from app.structured_data.adapters import ReadOnlySourceAdapter
from app.structured_data.sources import get_source_catalog

adapter = ReadOnlySourceAdapter(get_source_catalog().get("sap_hcm"))
print(adapter.validate_configuration())   # debe ser []
print(adapter.health_check())             # (True, 'CONNECTED_AND_VALIDATED')
```

---

## 7. Recomendaciones

1. **Exponer vistas, no tablas.** Una vista de seguridad en el propio motor es una
   segunda capa independiente del control aplicativo.
2. **Nunca conceder INSERT/UPDATE/DELETE** a la cuenta de Matrix RH, aunque el
   compilador ya lo impida: defensa en profundidad.
3. **Filtros organizacionales obligatorios** (`required_filters`) para acotar el
   alcance por centro, empresa o estatus.
4. **Excluir columnas sensibles** de `allowed_columns`: si el salario no está
   declarado, ningún plan puede proyectarlo.
5. **Timeout corto**: una consulta lenta bloquea un turno de chat.
6. **Rotar el DSN** sin tocar el repositorio: sólo cambia la variable de entorno.
