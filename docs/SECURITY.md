# Seguridad — Matrix RH

> Creado por Aldo Garcia.

Documento de controles implementados. El análisis de amenazas está en
[`THREAT_MODEL.md`](THREAT_MODEL.md).

---

## 1. Principios aplicados

- **Mínimo privilegio**: cada rol recibe exactamente lo que necesita; no existen
  permisos de "SQL arbitrario", "leer secretos" ni "ver el system prompt".
- **Deny-by-default**: la ausencia de una regla nunca concede acceso.
- **Defensa en profundidad**: cada control crítico está respaldado por al menos
  otro independiente.
- **Fail closed**: ante duda, error o dependencia caída, se deniega.

---

## 2. Autenticación

Ver [`AUTHENTICATION_AUTHORIZATION.md`](AUTHENTICATION_AUTHORIZATION.md).

Resumen: OIDC Authorization Code + PKCE con patrón BFF para Entra ID; proveedor
local con Argon2id restringido a `development`/`test`; sesión de servidor con
cookie `HttpOnly` y hash del token en la base; CSRF por token de sesión en toda
petición mutante; rate limiting por IP y por usuario; bloqueo temporal por
intentos fallidos; mensajes de error idénticos para usuario inexistente y
contraseña incorrecta.

---

## 3. Autorización

- `UserContext` inmutable y firmado con HMAC-SHA256.
- Decisión **antes** de RAG, **antes** del SQL y **antes** del prompt.
- El filtro de categorías viaja dentro de la consulta a Qdrant.
- Ownership estricto de conversaciones (404, no 403, ante recursos ajenos).
- La wildcard administrativa se resuelve a una lista enumerada; nunca se eliminan
  filtros.

---

## 4. Gestión de secretos

| Regla | Implementación |
|---|---|
| Ningún secreto en el código | Verificado por `scripts/secrets_scan.py` y `bandit` |
| Sólo `.env.example` en el repositorio | `.env` está en `.gitignore` |
| Secretos por entorno o gestor | `Settings` usa `SecretStr`; `pydantic-settings` lee del entorno |
| DSN de fuentes externas | `sources.yaml` guarda el **nombre** de la variable, nunca el valor |
| El frontend nunca recibe secretos | El bundle no contiene ninguna variable sensible; verificado en E2E |
| Sin tokens en `localStorage` | La sesión es cookie `HttpOnly`; verificado en E2E |
| Redacción en logs | Se aplica en el *formatter*, no en el llamador |

### Supresiones del escáner

Cada supresión requiere un marcador inline con justificación:

```python
# secrets-scan: allow (JWT sintetico sin firma valida, fixture de redaccion)
```

Todas las supresiones se publican íntegras en
`reports/security/secrets_scan.json` para revisión.

---

## 5. Criptografía

| Uso | Algoritmo | Nota |
|---|---|---|
| Contraseñas locales de test | **Argon2id** (t=3, m=64 MiB, p=2) | Nunca SHA para contraseñas |
| Integridad de documentos | SHA-256 | Huella para detectar cambios |
| Firma del `UserContext` | HMAC-SHA256 | Clave `APP_SECRET_KEY` |
| Token de sesión en la BD | SHA-256 del token | El token en claro sólo viaja en la cookie |
| Seudonimización en logs | HMAC-SHA256 truncado | Hash del conjunto de roles |
| TLS | 1.2 mínimo, 1.3 preferido | Terminado en el proxy |
| Cifrado aplicativo (si se requiere) | AES-256-GCM vía `cryptography` | La clave no vive en el repositorio |

Cookies: `HttpOnly` siempre; `Secure` obligatorio en producción (validado en la
configuración, el arranque falla si no); `SameSite` configurable con `lax` por
defecto.

---

## 6. Carga de archivos

1. Allowlist de extensiones (`.docx`, `.md`, `.pdf`, `.txt`, `.xlsx`, `.csv`).
2. Verificación de **magic bytes** frente a la extensión declarada.
3. Tamaño máximo configurable (25 MB por defecto) y máximo de archivos por
   petición.
4. Nombre interno UUID; el `filename` del cliente jamás se usa como ruta.
5. Normalización y bloqueo de `..`, rutas absolutas y unidades de Windows.
6. Almacenamiento fuera del web root (`var/uploads/<user>/<conversation>/`).
7. Límites anti-zip-bomb para OOXML: entradas, tamaño descomprimido y ratio.
8. Límites de páginas, hojas, filas y celdas en los extractores.
9. Sin ejecución de macros, fórmulas ni contenido incrustado.
10. Sanitización en el render (el frontend construye nodos React, no HTML).

**El lote completo se valida antes de tocar infraestructura**: un archivo
rechazado devuelve 415/413 aunque el almacén vectorial esté caído, y no queda
medio lote indexado.

---

## 7. Acceso a datos estructurados

El LLM **no envía SQL**. El flujo es:

```
plan JSON -> Pydantic (extra=forbid) -> QueryPolicyValidator
   -> compilador parametrizado -> verificación AST (sqlglot)
   -> timeout + row limit -> credencial read-only
```

Bloqueado por construcción: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`,
`CREATE`, `EXEC/CALL` no autorizado, múltiples sentencias, comentarios SQL,
`UNION` y subconsultas.

Sobre el uso de f-string en el ensamblado del SQL: los identificadores no pueden
viajar como parámetros en ningún motor. La mitigación es de tres capas
(allowlist → regex de identificador + citado → parámetros + re-verificación por
AST) y está documentada como riesgo residual aceptado en
`reports/security/cybersecurity.md`.

Recomendación operativa: usar **vistas de seguridad** en la propia base además del
control aplicativo.

---

## 8. Cabeceras y CSP

Aplicadas por el backend (no sólo por el proxy), porque el arranque por doble
clic no lleva proxy delante:

```
Content-Security-Policy: default-src 'self'; script-src 'self';
  style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:;
  connect-src 'self'; object-src 'none'; frame-ancestors 'none';
  base-uri 'self'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Cache-Control: no-store
Strict-Transport-Security: max-age=31536000; includeSubDomains   (si TLS)
```

`script-src` no incluye `unsafe-eval` ni `unsafe-inline`. `style-src` admite
`unsafe-inline` porque React inyecta estilos calculados; los scripts, que son el
vector real de XSS, no.

---

## 9. XSS en el frontend

El renderizador de Markdown (`frontend/src/security/Markdown.tsx`) **construye
elementos de React** en lugar de generar HTML. No se usa
`dangerouslySetInnerHTML` en ninguna parte del proyecto, por lo que un
`<img onerror=...>` incrustado en un documento corporativo o en una respuesta del
modelo se muestra como texto literal.

Además, una cita cuyo `source_id` no está en la lista de fuentes recibidas se
renderiza como texto plano, sin apariencia de fuente verificada.

---

## 10. Observabilidad y auditoría

Logs JSON con: `timestamp`, `request_id`, `conversation_id`, `user_opaque_id`,
`role_set_hash`, `intent`, `selected_model`, `selected_tools`, `source_ids`,
`authorization_decision`, `latency_ms`, `status`, `error_code`.

**No se registran**: contraseñas, client secrets, bearer tokens, llaves privadas,
documentos completos ni prompts completos.

`/health` (proceso vivo) y `/ready` (dependencias obligatorias operativas) tienen
semántica distinta a propósito: si `health` dependiera de MySQL, un reinicio de la
base tumbaría el contenedor entero.

---

## 11. Manejo de errores

Al cliente sólo llegan `code`, `message` y `request_id`. Nunca stack traces,
rutas internas, SQL ni secretos. Los errores de validación de Pydantic **no**
hacen eco del payload recibido: podría reflejar una credencial escrita por error
en un campo equivocado.

Códigos definidos: `unauthorized`, `forbidden`, `unsupported_file`,
`file_too_large`, `extraction_failed`, `ingestion_failed`, `ollama_unavailable`,
`embedding_dimension_mismatch`, `qdrant_unavailable`, `database_unavailable`,
`structured_query_rejected`, `insufficient_evidence`, `out_of_scope`,
`policy_missing`, `not_found`, `validation_error`, `rate_limited`,
`configuration_error`, `internal_error`.

---

## 12. Exposición de red

Sólo el proxy es accesible desde fuera. MySQL, Qdrant y Ollama escuchan en
`127.0.0.1`. **Ollama no debe exponerse a Internet ni a redes no confiables** —
carece de autenticación.

---

## 13. Cadena de suministro

El vector más peligroso del ecosistema npm hoy no es una vulnerabilidad en una
librería: es un **gusano autopropagable**. Un paquete comprometido ejecuta código
en el ciclo de vida de instalación, roba credenciales del entorno (`NPM_TOKEN`,
`GITHUB_TOKEN`, credenciales cloud) y republica paquetes del mantenedor afectado
para propagarse. La víctima no necesita ejecutar la aplicación: basta con
instalar.

> **El gestor por si solo no es la defensa.** El frontend se instala con npm.
> Lo que protege es no ejecutar scripts + lockfile congelado + la verificacion
> del arbol.

### El control central: no ejecutar scripts de instalación

```ini
# frontend/.npmrc  (lo leen npm y pnpm)
ignore-scripts=true
```

Con esa línea, **aunque un paquete comprometido entre al árbol, su código no se
ejecuta durante la instalación**. Es viable en este proyecto porque ninguna
dependencia necesita un script de instalación: se verifica automáticamente.

### Nunca sin banderas, siempre `npm ci --ignore-scripts`

| Comando | Comportamiento |
|---|---|
| `npm install` / `pnpm install` (sin flags) | Puede **resolver rangos** y traer una versión publicada hace minutos. Ejecuta scripts. |
| `npm ci --ignore-scripts` | Instala **exactamente** lo que fija `package-lock.json`. No ejecuta scripts. Falla si el lockfile no está sincronizado. |

Aplicado en `windows/Install-MatrixRH.ps1`, `scripts/matrixrh.sh`,
`backend/Dockerfile` y documentado en el README. El Dockerfile **no** tiene
fallback a una instalación sin fijar: si el lockfile está desincronizado, el
build falla en lugar de degradarse.

### Verificación automática del árbol instalado

Desde la raíz del proyecto:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.verify_supply_chain
```

Comprueba cuatro cosas sobre el árbol **realmente instalado**, no sobre el
manifiesto declarado:

1. **Lista de bloqueo** — ningún paquete/versión de
   `config/supply_chain_denylist.yaml` está presente, **a ninguna profundidad**
   (un paquete comprometido suele ser una dependencia transitiva).
2. **Scripts de instalación** — ningún paquete declara `preinstall`, `install`
   ni `postinstall`.
3. **Indicadores de compromiso** — nombres de archivo y patrones de contenido
   asociados a exfiltración: `webhook.site`, `npmjs.help`,
   `api.github.com/user/repos`, lectura de `NPM_TOKEN`/`GITHUB_TOKEN` seguida de
   una petición de red.
4. **Reproducibilidad** — existe `package-lock.json` y `.npmrc` declara
   `ignore-scripts=true`.
5. **Version del gestor** — `packageManager` fija una version exacta de npm,
   que ya viene distribuido con Node.

Se ejecuta en el **preflight** (cada arranque), en el **instalador** (bloquea la
compilación si falla), en el **quality gate** y en `windows\Validate-MatrixRH.ps1`.

### Riesgos del gestor y su mitigación

El frontend usa **npm**, incluido en Node, con version fijada en
`packageManager`:

| Riesgo | Mitigación |
|---|---|
| `package-lock.json` desincronizado | `npm ci` falla cerrado y no modifica el lock. |
| Scripts de ciclo de vida comprometidos | `.npmrc` y la CLI fuerzan `ignore-scripts=true`. |
| Version distinta del gestor | `packageManager` declara `npm@10.9.0` y el harness la hace visible. |

Para instalar el arbol exacto:

```bash
npm ci --ignore-scripts
```

El control está cubierto por pruebas que construyen árboles sintéticos con un
paquete comprometido, un `postinstall` y un IOC, y verifican que **dispara**
(`tests/security/test_supply_chain.py`). Un control que nunca falla no vale nada.

El control está cubierto por 19 pruebas que construyen árboles sintéticos con un
paquete comprometido, un `postinstall` y un IOC, y verifican que **dispara**
(`tests/security/test_supply_chain.py`). Un control que nunca falla no vale nada.

### Mantener la lista de bloqueo

`config/supply_chain_denylist.yaml` es datos, no código. Cuando se publique un
incidente nuevo, añada el paquete y las versiones afectadas. Acepta versión
exacta, lista de versiones o el comodín `*`.

### Auditoría de vulnerabilidades

| Comando | Umbral |
|---|---|
| `npm audit --omit=dev --audit-level low` | **Bloqueante**: es lo que se despliega |
| `npm audit` (incluye dev) | Informativo pero visible; no se oculta |
| `pip-audit --strict` | Informativo, revisado por el Agente de Ciberseguridad |
| `bandit -r app` | Bloqueante |

Estado actual: **0 vulnerabilidades** en ambos modos de `npm audit`.

### Resto de la cadena

- Dependencias con versión **fija** (`==` en Python, exacta en el frontend) y `save-exact=true`.
- Registro oficial forzado en `.npmrc`: un `.npmrc` heredado no puede apuntar a
  un espejo.
- Extras opcionales para drivers de motores no usados: reducen la superficie.
- Playwright descarga navegadores sólo de forma **explícita**
  (`npm run e2e:install`), nunca implícita al instalar.

---

## 14. Reporte de vulnerabilidades

Ver [`../SECURITY.md`](../SECURITY.md) en la raíz del repositorio.
