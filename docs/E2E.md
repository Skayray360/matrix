# Pruebas End-to-End — Matrix RH

> Creado por Aldo Garcia.

Playwright contra el backend real sirviendo el frontend compilado *same-origin*
(`http://127.0.0.1:8000`). Es la misma topología que ve el usuario al arrancar
con `INICIAR_MATRIX_RH.bat`, de modo que la prueba valida el despliegue real y no
una maqueta.

---

## 1. Ejecución

```bash
INICIAR_MATRIX_RH.bat -NoBrowser
```
```bat
cd frontend
npm run e2e
```

Primera vez, instalar el navegador:

```bat
cd frontend
npm run e2e:install
```

`windows\Validate-MatrixRH.ps1` arranca el backend, ejecuta Playwright y lo detiene.

Los timeouts son generosos (240 s por prueba) **a propósito**: un turno con el
modelo profundo puede tardar varios minutos si `qwen3.6:latest` no cabe entero en
la GPU del equipo. No es inestabilidad de la interfaz.

---

## 2. Cobertura de los flujos críticos

| # | Flujo | Archivo |
|---|---|---|
| 1 | Login exitoso | `01-auth.spec.ts` |
| 2 | Login rechazado / no autorizado | `01-auth.spec.ts` |
| 3 | Usuario general pregunta conocimiento general | `02-authorization.spec.ts` |
| 4 | Usuario general intenta acceder a nómina restringida y no recibe contenido | `02-authorization.spec.ts` |
| 5 | Usuario con rol permitido sí recibe contenido y fuentes | `02-authorization.spec.ts` |
| 6 | Subir MD en chat, esperar ingesta y preguntar sobre él | `03-documents-memory.spec.ts` |
| 7 | Subir TXT y validar extracción | `03-documents-memory.spec.ts` |
| 8 | Continuar conversación tras recarga | `03-documents-memory.spec.ts` |
| 9 | Nueva conversación sin contaminar memoria | `03-documents-memory.spec.ts` |
| 10 | Usuario A no puede abrir conversación de usuario B | `02-authorization.spec.ts` |
| 11 | Ruta rápida usa Gemma en caso simple | `04-operations.spec.ts` |
| 12 | Ruta profunda usa Qwen en caso complejo | `04-operations.spec.ts` |
| 13 | Diagnóstico expone parámetros y ningún secreto | `04-operations.spec.ts` |
| 14 | Prompt injection en documento no altera reglas | `03-documents-memory.spec.ts` |
| 15 | Errores manejados sin fuga de stack ni secretos | `04-operations.spec.ts` |
| 16 | Error de dependencia manejado de forma controlada | `04-operations.spec.ts` |
| 19 | Categoría nueva queda deny-by-default | `04-operations.spec.ts` |
| 20 | Logout invalida la sesión | `01-auth.spec.ts` |
| 21 | Login `Matrix` / `Matrix RH` en modo local | `01-auth.spec.ts` |
| 22 | Login `MatrixR1` / `Matrix RH` en modo local | `01-auth.spec.ts` |
| 23 | `Matrix` recupera y cita las cinco categorías | `02-authorization.spec.ts` |
| 24 | **GATE CRÍTICO** `MatrixR1` recupera y cita `prestaciones` | `02-authorization.spec.ts` |
| 25 | **GATE CRÍTICO** `MatrixR1` recibe DENY en `nomina` | `02-authorization.spec.ts` |
| 26 | `MatrixR1` recibe DENY en `reclutamiento` | `02-authorization.spec.ts` |
| 27 | `MatrixR1` recibe DENY en `relaciones_laborales` | `02-authorization.spec.ts` |
| 28 | `MatrixR1` recibe DENY en `salud_ambiental` | `02-authorization.spec.ts` |
| 29 | `MatrixR1` no puede listar ni inferir documentos restringidos | `02-authorization.spec.ts` |
| 30 | Manipular `role`, `groups`, `user_id` desde el cliente no eleva permisos | `01-auth.spec.ts` |
| 33 | Contraseña incorrecta no revela si el usuario existe | `01-auth.spec.ts` |

### Flujos verificados fuera de Playwright

Algunos gates se validan de forma más fiable en otra suite; se documenta dónde:

| # | Flujo | Dónde se verifica | Por qué |
|---|---|---|---|
| 17 | Archivo modificado se reindexa sin duplicar chunks | `scripts.bootstrap ingest` + `documents.chunk_count` | Requiere manipular el sistema de archivos entre ejecuciones |
| 18 | Archivo eliminado retira sus vectores | `IngestionService.delete_document` + `reconcile_knowledge` | Ídem |
| 31 | `local_test` deshabilitado en producción | `tests/unit/test_config.py::TestSeguridadDeEntorno` | Exige arrancar con `APP_ENV=production`, que por diseño **falla**; comprobarlo en unitarias es determinista |
| 32 | El mismo contrato de autorización pasa con identidad local y con claims Entra simulados | `tests/unit/test_authorization.py` + adapter Entra con JWKS local | No hay tenant real disponible |
| 34 | El hash almacenado es Argon2id y no texto plano | `tests/integration/test_schema_and_seed.py` | Requiere leer la base directamente |
| 35 | Identidad exacta, ruta general/documental y resumen privado completo | `tests/unit/test_ai_runtime_contracts.py` | Permite inyectar modelos/store deterministas y probar fallos difíciles de provocar en UI |
| 36 | Perfiles HCM acumulativos, revocación y segregación de Nómina | `tests/unit/test_access_profile_contract.py` + `test_entra_role_sync.py` | Entra real no está conectado en el paquete |
| 37 | Administrador funcional no publica ni enumera otro dominio | `tests/unit/test_admin_category_scope.py` | Verifica el guard antes de leer/escribir el archivo |

---

## 3. Convenciones de los specs

- Los `data-testid` de la interfaz son parte del contrato de prueba:
  `identity-user`, `identity-source`, `identity-scope`, `conversation-list`,
  `new-conversation`, `composer-input`, `send-button`, `message-user`,
  `message-assistant`, `message-pending`, `sources`, `attachments`,
  `error-banner`, `login-error`, `citation`.
- `helpers.ts` centraliza `login`, `ask`, `logout` y `assertNoRestrictedLeak`.
- Las credenciales sintéticas se declaran como constantes con su advertencia.

---

## 4. Evidencia

| Artefacto | Ruta |
|---|---|
| Resultados JSON | `reports/tests/playwright-results.json` |
| Reporte HTML | `frontend/playwright-report/` |
| Trazas de fallos | `frontend/test-results/` |
| Capturas de fallos | `frontend/test-results/` |
| Resumen de validación | `reports/final-validation.json` |

---

## 5. Requisitos previos

1. Backend arriba y `/ready` en `true`.
2. Conocimiento indexado (`scripts.bootstrap ingest`).
3. Usuarios sintéticos creados (`scripts.bootstrap seed`).
4. Frontend compilado (`npm run build`).
5. `AUTH_PROVIDER=local_test` con `APP_ENV=development` o `test`.
