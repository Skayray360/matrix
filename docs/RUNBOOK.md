# Runbook operativo — Matrix RH

> Creado por Aldo Garcia.

---

## 1. Operaciones diarias

| Tarea | Comando |
|---|---|
| Arrancar | `INICIAR_MATRIX_RH.bat` |
| Detener | `DETENER_MATRIX_RH.bat` |
| Estado rápido | `DIAGNOSTICO_MATRIX_RH.bat` |
| Estado en JSON | `DIAGNOSTICO_MATRIX_RH.bat -Json` |
| Validación completa | `windows\Validate-MatrixRH.ps1` |

Endpoints de salud:

| Endpoint | Significado |
|---|---|
| `GET /health` | El proceso está vivo. No toca dependencias |
| `GET /ready` | Todas las dependencias obligatorias están operativas |

---

## 2. Publicar conocimiento corporativo

**Opción A — sistema de archivos** (recomendada para cargas masivas):

1. Copiar los archivos generales a `data/knowledge/general/<tema>/` y los de
   acceso por área a `data/knowledge/especializadas/<dominio>/`. Nómina General
   y Nómina Confidencial deben permanecer en dominios separados.
2. Esperar a la reconciliación automática (24 h) o forzarla:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap ingest
```

**Opción B — API administrativa** (requiere `knowledge.admin` y categoría
efectiva):

`POST /api/v1/admin/knowledge/documents` con `category` y el archivo.

El backend rechaza una categoría fuera del alcance del administrador y escribe
la ruta oficial: `general/<archivo>` para `general` o
`especializadas/<dominio>/<archivo>` para el resto. El resumen administrativo
también devuelve sólo categorías efectivas.

---

La estructura y el checklist de publicación están en
[`DOCUMENTATION_GOVERNANCE.md`](DOCUMENTATION_GOVERNANCE.md).

---

## 3. Alta de un dominio especializado

1. Definir el slug en minúsculas, dígitos, `_` o `-`.
2. Declarar sensibilidad, propietario, elegibilidad de wildcard y grupos en
   `config/authorization/categories.yaml`.
3. Mapear sus grupos `HCM_ADM_*` y `HCM_COORD_*` a roles internos.
4. Conceder esos roles en `category_permissions`.
5. Crear `data/knowledge/especializadas/<dominio>/` y copiar documentación ya
   clasificada.
6. Ejecutar la reconciliación y comprobar `documents.status = indexed`.
7. Probar un perfil autorizado y uno no autorizado antes de liberar el dominio.

La carpeta queda **deny-by-default** y fuera del wildcard hasta que las reglas
sean explícitas. Un dominio sensible usa `wildcard_eligible: false`. Nómina
Confidencial siempre se prueba y concede por separado de Nómina General.

---

## 4. Alta de un usuario (con Entra ID activo)

1. Asignar `HCM_EMP_BASICO_MX` y después los grupos funcionales acumulativos que
   correspondan. Un especializado sin base no es una identidad válida.
2. El primer login crea el `users` + `identity_links` y aplica el mapeo de
   `entra_group_role_mappings`.
3. Si ningún grupo mapea a un rol, el usuario queda **sin permisos**: es el
   comportamiento diseñado.

Verificar con `GET /api/v1/me`; la lista debe ser la unión exacta de concesiones,
sin categorías de otro módulo. Matriz: [`ACCESS_PROFILES.md`](ACCESS_PROFILES.md).

---

## 5. Revocar acceso

| Alcance | Acción |
|---|---|
| Rol local/no gobernado por Entra | Eliminar la fila de `user_roles`; el siguiente request ya no lo tiene |
| Perfil Entra | Retirar grupo/app role, revocar sesiones si el corte es inmediato y volver a autenticar |
| Una categoría | Eliminar la fila de `category_permissions` |
| Sesiones vivas | `revoke_all_user_sessions(db, user_id)` |
| Cuenta completa | `users.is_active = 0` |

Los permisos internos se releen desde la base **en cada request**. Los claims de
Entra se sincronizan al login: retirar un grupo elimina su rol gobernado en el
siguiente login, o inmediatamente después de revocar sesiones y exigir nueva
autenticación.

---

## 6. Alta de una fuente estructurada

1. Declararla en `config/data_sources/sources.yaml`: motor, `secret_ref`,
   entidades, columnas permitidas y filtros obligatorios.
2. Definir la variable de entorno con el DSN de una cuenta **read-only**.
3. Instalar el extra del driver si aplica:

```bat
cd backend
set "UV_PROJECT_ENVIRONMENT=%CD%\..\.venv"
uv sync --frozen --extra mssql
cd ..
```

4. Poner `enabled: true`.
5. Declarar el rol en `allowed_roles`. Para perfiles HCM, ejecute primero
   `scripts.load_entra_mapping --dry-run` y después `--prune`; el cargador
   reconcilia `structured_source_permissions` sin concesiones manuales huérfanas.
6. Confirmar que el rol también tenga `structured.query`.
7. Verificar en `GET /api/v1/admin/diagnostics` que aparece como
   `CONNECTED_AND_VALIDATED`.

Contrato inicial: `hcm_adm_ia_matrix` recibe `rh_demo` y
`postgres_analytics`; `hcm_adm_admpersonal` recibe `sap_hcm` y `oracle_hcm`.
Ningún `hcm_coord_*` recibe fuentes ni `structured.query`.

Detalle por motor en
[`integrations/DATABASE_CONNECTORS.md`](integrations/DATABASE_CONNECTORS.md).

---

## 7. Scheduler de 24 horas

- Se activa con `SCHEDULER_ENABLED=true` (por defecto).
- Intervalo: `RAG_REINDEX_INTERVAL_HOURS`.
- Protegido por un lock en `job_locks` con expiración de 60 min.
- Cada ejecución deja un registro en `ingestion_jobs` con estadísticas y errores.

Consultar la última ejecución:

```sql
SELECT status, trigger_source, started_at, finished_at, stats
FROM ingestion_jobs ORDER BY started_at DESC LIMIT 5;
```

---

## 8. Rotación de secretos

| Secreto | Efecto de rotarlo |
|---|---|
| `APP_SECRET_KEY` | Invalida todas las firmas de contexto y las sesiones. Los usuarios vuelven a entrar |
| `ENTRA_CLIENT_SECRET` | Sin impacto en sesiones vivas; el siguiente login usa el nuevo |
| DSN de una fuente | Reiniciar el backend para que el pool tome el nuevo |
| Contraseña de MySQL | Actualizar `DATABASE_URL` y reiniciar |

Ninguno de estos valores se guarda en el repositorio ni en la base.

---

## 9. Respaldo y restauración

```bash
mysqldump -u root matrix_rh_app > respaldo-matrix-rh.sql
```

Restaurar:

```bash
mysql -u root matrix_rh_app < respaldo-matrix-rh.sql
```

Después, aplicar migraciones y reindexar:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap setup
```

El índice vectorial **no requiere respaldo**: se reconstruye desde
`data/knowledge/`.

---

## 10. Métricas que conviene vigilar

| Métrica | Fuente | Señal de alarma |
|---|---|---|
| `latency_ms` de `chat.answer` | `audit_events` | Subida sostenida → el router escala a la ruta profunda con demasiada frecuencia |
| `status = insufficient_evidence` | `audit_events` | Alto → falta documentación o el chunking necesita revisión |
| `authorization_decision = DENY` | `audit_events` | Picos → un usuario explorando fuera de su alcance |
| `failure_count` de reconciliación | `ingestion_jobs` | > 0 → documentos que no se pueden procesar |
| `documents.status = failed` | tabla `documents` | Documentos rotos o protegidos |
