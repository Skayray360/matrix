# Activar Microsoft Entra ID — Matrix RH

> Creado por Aldo Garcia.
> Estado del paquete: **`PREPARED_NOT_CONNECTED`**. El adaptador y sus pruebas de
> contrato están incluidos; la conexión real requiere datos y aprobación del
> tenant corporativo.

## 1. Contrato de acceso antes de configurar el tenant

Toda identidad habilitada necesita el perfil base `HCM_EMP_BASICO_MX`. Los
perfiles especializados se acumulan; no lo sustituyen. Por ejemplo:

```text
HCM_EMP_BASICO_MX + HCM_COORD_RECLUTAMIENTO_MX
```

Un perfil `HCM_ADM_*`, `HCM_COORD_*` o futuro `HCM_COORD_CORE_*` sin el base
falla cerrado. Nómina General y Nómina Confidencial se asignan con valores
distintos y no se heredan entre sí. La matriz completa está en
[`../ACCESS_PROFILES.md`](../ACCESS_PROFILES.md).

## 2. Registrar la aplicación BFF

En Microsoft Entra ID cree o seleccione un **App registration** de un solo
tenant:

| Campo | Valor |
|---|---|
| Nombre | `Matrix RH` |
| Tipo de cuenta | Sólo cuentas de este directorio |
| Plataforma | **Web**, no SPA |
| Redirect URI | `https://<host>/api/v1/auth/callback` |

Anote `Application (client) ID` y `Directory (tenant) ID`. En **Authentication**:

- registre el redirect URI exacto, incluido esquema y puerto;
- no habilite *Implicit grant*;
- use Authorization Code + PKCE; el canje se realiza en el backend;
- configure `https://<host>/` como salida posterior si corresponde.

Los tokens no llegan al navegador. Matrix RH entrega una cookie de sesión opaca
`HttpOnly` después de validar `state`, `nonce`, PKCE, firma, issuer, audience y
expiración.

## 3. Elegir app roles o grupos

### Opción A — app roles (contrato distribuido)

Defina app roles cuyo **Value** coincida exactamente con los valores `HCM_*` de
`config/authorization/entra-role-mapping.yaml`. Cree al menos el base y sólo los
especializados que vaya a habilitar. En el token llegarán en `roles`.

Esta opción evita depender del claim `groups` y funciona mejor en directorios
con muchas pertenencias. No cambie `external_kind: app_role` en el YAML.

### Opción B — grupos de seguridad

Cree grupos dedicados y asigne siempre el base junto con los especializados.
En el YAML sustituya cada `external_key` usado por el **object ID** real del
grupo y cambie `external_kind` a `group`. El nombre visible no es una clave
estable ni se acepta como sustituto del object ID.

Configure el claim de grupos como **Group ID**. Si Entra omite la lista por
*group overage*, este adaptador no consulta Microsoft Graph: use app roles o
reduzca los grupos emitidos.

No configure las dos opciones para el mismo alcance sin una prueba de
deduplicación y revocación.

## 4. Secreto o certificado

Si la política exige un cliente confidencial, cree un secreto o certificado y
guárdelo en el gestor de secretos del entorno. Nunca lo escriba en el
repositorio, en documentación, tickets o mensajes de soporte. El backend también
admite cliente público con PKCE cuando la política corporativa lo permita.

## 5. Variables de runtime

Configure valores reales fuera del repositorio:

```dotenv
APP_ENV=production
AUTH_PROVIDER=entra
LOCAL_TEST_AUTH_ENABLED=false
LOCAL_TEST_SEED_USERS_ENABLED=false
SESSION_COOKIE_SECURE=true

ENTRA_TENANT_ID=<directory-tenant-id>
ENTRA_CLIENT_ID=<application-client-id>
ENTRA_CLIENT_SECRET=<sólo-si-aplica>
ENTRA_REDIRECT_URI=https://<host>/api/v1/auth/callback
ENTRA_POST_LOGOUT_REDIRECT_URI=https://<host>/
ENTRA_ROLE_MAPPING_FILE=./config/authorization/entra-role-mapping.yaml
```

`ENTRA_ALLOWED_GROUPS` es una barrera opcional que compara únicamente **object
IDs del claim `groups`**. Déjelo vacío si usa sólo app roles; configurarlo con
valores `HCM_*` en ese modo rechazaría todas las cuentas.

## 6. Validar y cargar el mapeo

Desde la raíz del proyecto, con la base interna disponible:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --dry-run
```

Revise que cada valor externo apunte al rol interno correcto. Después aplique y
retire mapeos obsoletos:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --prune
```

El cargador valida nombres, categorías y permisos, crea o reconcilia los roles,
sincroniza `entra_group_role_mappings` y materializa las fuentes declaradas en
`sources.yaml`. El contrato inicial concede `rh_demo`/`postgres_analytics` sólo
a `hcm_adm_ia_matrix` y `sap_hcm`/`oracle_hcm` sólo a
`hcm_adm_admpersonal`; ningún coordinador recibe `structured.query`.
`--prune` es intencional: revise el diff de ambos YAML antes de usarlo.

## 7. Comprobación técnica

1. Ejecute `DIAGNOSTICO_MATRIX_RH.bat` y corrija el primer `FAIL`.
2. Inicie Matrix RH y complete un login con perfil base únicamente.
3. Compruebe en `GET /api/v1/me` que sólo aparece `general`.
4. Pruebe base + un coordinador: debe sumar únicamente su dominio.
5. Pruebe Nómina General y Confidencial con cuentas distintas, incluyendo casos
   negativos.
6. Retire un perfil especializado en Entra y fuerce un nuevo login: el rol
   administrado obsoleto debe desaparecer.
7. Pruebe un especializado sin base: no debe recibir ningún rol HCM efectivo.

La sincronización de claims ocurre en el login. Una revocación del directorio se
observa al siguiente login; para corte inmediato revoque también las sesiones
activas según el runbook.

## 8. Retirar el proveedor local

Antes de producción, desactive las cuentas sintéticas y valide que no queda una
credencial local activa. Con `APP_ENV=production`, Matrix RH impide el arranque
si `AUTH_PROVIDER=local_test`, si el seed local está activo o si la cookie no es
segura.

## 9. Problemas frecuentes

| Síntoma | Causa probable | Acción |
|---|---|---|
| `AADSTS50011` | Redirect URI distinto | Copiar exactamente el URI registrado |
| Login correcto, sin categorías | Ningún valor de `groups`/`roles` mapea | Comparar el claim con `external_key` y recargar YAML |
| Especializado queda sin acceso | Falta `HCM_EMP_BASICO_MX` | Asignar el perfil base; no relajar el fail-closed |
| Todas las cuentas reciben 401 con app roles | `ENTRA_ALLOWED_GROUPS` contiene valores que no son object IDs emitidos | Dejarlo vacío o usar grupos reales |
| Token no contiene todos los grupos | *Group overage* | Usar app roles; el adaptador no hace fallback a Graph |
| Permiso retirado sigue durante una sesión | La sincronización ocurre al login | Revocar sesiones y volver a autenticar |
| `state` inválido | Expiró o se reutilizó | Reiniciar el flujo de login |

Plan de transición y reversión:
[`MIGRATE_LOCAL_TEST_TO_ENTRA.md`](MIGRATE_LOCAL_TEST_TO_ENTRA.md).
