# Estado de dependencias externas — Matrix RH

> Creado por Aldo Garcia.

Estados permitidos (sección 37 de la especificación):

| Estado | Significado |
|---|---|
| `CONNECTED_AND_VALIDATED` | Se realizó una conexión real satisfactoria |
| `PREPARED_NOT_CONNECTED` | El adapter existe, valida configuración, tiene health check y pruebas de contrato, pero **no** se ha conectado |
| `DISABLED` | Declarado y deshabilitado a propósito |
| `ERROR` | Configurado pero la conexión falla |

**Nunca se declara `CONNECTED_AND_VALIDATED` sin haber conectado de verdad.**

---

## 1. Estado de validación del paquete 1.1.0

No se hereda una conexión medida en versiones anteriores. Las pruebas offline
1.1.0 están aprobadas, pero esta sesión no levantó la topología Windows:

| Integración | Estado para esta entrega | Cómo se cierra |
|---|---|---|
| Ollama `gemma4:latest` | pendiente de validación live 1.1.0 | `GET /api/tags` + generación real |
| Ollama `qwen3.6:latest` | pendiente de validación live 1.1.0 | `GET /api/tags` + generación real |
| Ollama `embeddinggemma:latest` | pendiente de validación live 1.1.0 | `/api/embed`, dimensión real 768 |
| MySQL/MariaDB interna | pendiente de validación live 1.1.0 | migraciones, seed y consultas en WAMP destino |
| Qdrant (modo `embedded`) | pendiente de validación live 1.1.0 | colección, upsert, scroll y búsqueda ACL |
| Qdrant (modo `server`) | `DISABLED` por defecto | habilitar sólo con instancia dedicada |
| **Microsoft Entra ID** | `PREPARED_NOT_CONNECTED` | tenant, app registration y login real |
| SQL Server (`sap_hcm`) | `PREPARED_NOT_CONNECTED` | DSN read-only + health check |
| Oracle (`oracle_hcm`) | `PREPARED_NOT_CONNECTED` | DSN read-only + health check |
| PostgreSQL (`postgres_analytics`) | `PREPARED_NOT_CONNECTED` | DSN read-only + health check |
| MySQL demo (`rh_demo`) | `PREPARED_NOT_CONNECTED` | habilitar conscientemente y configurar DSN |

El estado en runtime se consulta en `GET /api/v1/admin/diagnostics` y en
`DIAGNOSTICO_MATRIX_RH.bat`.

---

## 2. Microsoft Entra ID

### Qué está entregado

| Elemento | Ubicación |
|---|---|
| Puerto de dominio | `backend/app/auth/provider.py::IdentityProvider` |
| Adapter concreto (OIDC + PKCE + BFF) | `backend/app/auth/entra_provider.py` |
| Configuración tipada y validada | `backend/app/config/settings.py` |
| Validación de variables obligatorias | `Settings._validate_environment_safety` |
| Health check | `EntraIdentityProvider.status()` |
| Mapeo de grupos a roles | `entra_group_role_mappings` + `config/authorization/entra-role-mapping.yaml` |
| Estado operativo visible | `/ready` y `/admin/diagnostics` |
| Documentación paso a paso | [`integrations/ENTRA_ID_SETUP.md`](integrations/ENTRA_ID_SETUP.md) |
| Guía de migración | [`integrations/MIGRATE_LOCAL_TEST_TO_ENTRA.md`](integrations/MIGRATE_LOCAL_TEST_TO_ENTRA.md) |

### Qué falta para `CONNECTED_AND_VALIDATED`

Tenant, App Registration, redirect URI y (si es cliente confidencial) secreto o
certificado. Nada de eso puede inventarse.

### Qué garantiza el modo actual

El contrato de autorización se valida hoy con `Matrix` y `MatrixR1` sobre el
mismo `PolicyEngine` que usará Entra ID. Cuando se conecte el tenant, sólo cambia
de dónde viene la identidad; roles, categorías y políticas se reutilizan tal cual.

---

## 3. Bases de datos externas

### Qué está entregado

| Elemento | Ubicación |
|---|---|
| Puerto/adapter read-only genérico | `backend/app/structured_data/adapters.py` |
| Validación de configuración sin conectar | `ReadOnlySourceAdapter.validate_configuration()` |
| Prueba de conexión | `ReadOnlySourceAdapter.health_check()` |
| Timeout por motor | `_connect_args()` |
| Allowlist de entidades y columnas | `config/data_sources/sources.yaml` |
| Bloqueo de DDL/DML | `compiler.verify_sql_is_readonly` |
| Prohibición de SQL libre del LLM | `StructuredQueryPlan` + `QueryPolicyValidator` |
| Documentación por motor | [`integrations/DATABASE_CONNECTORS.md`](integrations/DATABASE_CONNECTORS.md) |

Los drivers de motores no usados localmente son **extras opcionales** del
paquete (`.[oracle]`, `.[mssql]`, `.[postgres]`), pero el adapter, su validación,
su health check y sus pruebas existen siempre.

### Qué falta

DSN de una cuenta read-only por fuente y conectividad de red hacia el servidor.

---

## 4. Impacto en la entrega

Una dependencia externa opcional no disponible **no bloquea** la construcción
técnica, siempre que:

1. quede marcada explícitamente como `PREPARED_NOT_CONNECTED`;
2. el modo sintético equivalente permita probar la lógica interna;
3. no se declare una integración real inexistente.

Las pruebas offline cubren identidad, autorización, plan, validador y compilador.
Esto no sustituye los gates obligatorios del producto local: Ollama,
MySQL/MariaDB y Qdrant deben quedar en `CONNECTED_AND_VALIDATED` en el equipo
destino antes de aceptar la entrega.

---

## 5. Dónde más está documentado este estado

- `README.md`, sección 12
- `docs/RUNBOOK.md`, sección 6
- `config/data_sources/README.md`
- `docs/integrations/README.md`
- `GET /api/v1/admin/diagnostics` en runtime
