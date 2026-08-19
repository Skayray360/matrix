# Migración de `local_test` a Microsoft Entra ID

> Creado por Aldo Garcia.

Cambiar el proveedor de identidad no reescribe RAG, agentes, frontend ni
políticas. Sí cambia el origen de identidad, el contrato de roles y la gestión de
sesiones. Haga la transición primero en un entorno de pruebas corporativo.

## 1. Contrato que debe conservarse

| Regla | Resultado esperado |
|---|---|
| Perfil base | Toda identidad incluye `HCM_EMP_BASICO_MX` |
| Perfiles especializados | Se agregan al base; nunca lo reemplazan |
| Alcance por dominio | Cada `HCM_ADM_*` o `HCM_COORD_*` suma sólo su módulo |
| Administración documental | `knowledge.admin` se intersecta con categorías efectivas |
| Nómina | General y Confidencial permanecen separadas |
| Revocación | El siguiente login retira roles Entra obsoletos |
| Ausencia de mapeo | No concede permisos |

Los roles `matrix_admin_test` y `prestaciones_reader_test` son fixtures locales;
no son perfiles corporativos ni deben mapearse desde Entra. El contrato HCM vive
en `config/authorization/entra-role-mapping.yaml`.

## 2. Línea base y reversión

Antes de cambiar:

1. ejecute `windows\Validate-MatrixRH.ps1` y preserve el reporte aprobado;
2. respalde la base interna y el archivo de configuración privado mediante el
   proceso de su organización;
3. documente qué cuentas de prueba validan cada dominio sin incluir datos
   personales en el repositorio;
4. confirme cómo revocará sesiones si necesita un corte inmediato.

La reversión consiste en detener el servicio, restaurar la configuración previa
de un entorno no productivo y arrancar de nuevo. Nunca reactive `local_test` en
producción ni restaure credenciales conocidas en un host productivo.

## 3. Preparar Entra ID

Complete [`ENTRA_ID_SETUP.md`](ENTRA_ID_SETUP.md) hasta validar los app roles o
grupos. Verifique en particular:

- redirect URI Web exacto y Authorization Code + PKCE;
- app roles `HCM_*` o object IDs reales de grupos, no nombres visibles;
- perfil base asignado a toda identidad habilitada;
- perfiles independientes para Nómina General y Confidencial;
- secretos fuera del repositorio.

## 4. Revisar y sincronizar el contrato HCM

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --dry-run
```

Después de aprobar el contrato:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --prune
```

El segundo comando modifica la base: crea o actualiza roles declarados,
reconcilia sus categorías/permisos y elimina mapeos que ya no estén en el YAML.
No use `--allow-placeholders` fuera de pruebas automatizadas.

## 5. Conmutar en staging

```dotenv
APP_ENV=staging
AUTH_PROVIDER=entra
LOCAL_TEST_AUTH_ENABLED=false
LOCAL_TEST_SEED_USERS_ENABLED=false
SESSION_COOKIE_SECURE=true
```

Complete las variables `ENTRA_*`, ejecute `DIAGNOSTICO_MATRIX_RH.bat`, inicie el
sistema y pruebe:

| Escenario | Resultado |
|---|---|
| Sólo perfil base | `allowed_categories` contiene sólo `general` |
| Base + coordinador de un módulo | `general` + ese dominio, sin otros |
| Base + administrador de un módulo | Puede publicar sólo en su categoría efectiva |
| Nómina General | No ve títulos, conteos ni contenido de Confidencial |
| Nómina Confidencial | Requiere su grupo nominal; no depende del wildcard |
| Especializado sin base | Sin roles HCM efectivos |
| Grupo no mapeado | Sin permisos añadidos |
| Grupo retirado + nuevo login | Rol administrado retirado |
| Conversación ajena | 404 |
| Claims/cabeceras manipulados por cliente | Sin elevación |

Ejecute después `windows\Validate-MatrixRH.ps1` y compare el reporte con la línea base.

## 6. Revocar el modo local

Antes de producción:

1. desactive las cuentas marcadas `is_synthetic_test`;
2. retire sus credenciales locales mediante un cambio administrado;
3. confirme que no quedan sesiones de prueba activas;
4. mantenga `LOCAL_TEST_AUTH_ENABLED=false` y
   `LOCAL_TEST_SEED_USERS_ENABLED=false`;
5. arranque con `APP_ENV=production` y verifique que `/ready` aprueba.

El validador de configuración impide producción con proveedor local, seed local
o cookie insegura. No fuerce ni elimine esa protección para completar la
migración.

## 7. Revocación posterior

Retirar un grupo o app role en Entra actualiza los roles administrados cuando la
persona vuelve a autenticarse. Matrix RH conserva sólo roles no gobernados por
ese mapeo. Si la revocación debe ser inmediata, revoque además todas las sesiones
del usuario; en su siguiente request deberá autenticarse y se sincronizará el
nuevo conjunto.

La memoria conversacional se filtra con las categorías efectivas actuales. Un
alcance retirado no debe volver a entrar al prompt desde el historial.
