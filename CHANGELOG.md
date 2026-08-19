# Changelog — Matrix RH

> Creado por Aldo Garcia.
> Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

---

## [Sin publicar]

### Cambiado

- **Lanzadores consolidados.** `INSTALAR_MATRIX_RH.bat` pasa a ser el único
  instalador: instala **e inicializa** (al terminar arranca el backend, espera
  `/health` y `/ready`, sirve la interfaz y abre el navegador). Se conservan
  `INICIAR`, `DETENER` y `DIAGNOSTICO`.
- El instalador de shell `scripts/matrixrh.sh` se alinea con el instalador de
  Windows: `uv sync --frozen` (antes `pip install -e`) y verificación de cadena
  de suministro antes de compilar el frontend. Cierra una divergencia de
  reproducibilidad y del control antigusano en entornos no-Windows.
- **Gestor del frontend migrado de npm a pnpm** (vía corepack, versión fijada en
  `packageManager`). Toda instalación usa
  `corepack pnpm install --frozen-lockfile --ignore-scripts`; auditoría con
  `pnpm audit`. Se actualizaron Dockerfile, `Install-MatrixRH.ps1`,
  `Validate-MatrixRH.ps1`, `matrixrh.sh`, `run_quality_gate.py`, `preflight.py`,
  `verify_supply_chain.py` (lockfile `pnpm-lock.yaml`, con `package-lock.json`
  aceptado como fallback transitorio), pruebas y documentación. El control
  antigusano (`ignore-scripts` + lockfile congelado + verificación del árbol)
  es idéntico: pnpm usa el mismo registro que npm y no elimina el riesgo por sí
  solo; la protección real no cambia.
- **Integridad del gestor (corepack).** `verify_supply_chain` comprueba que
  `packageManager` fije pnpm con hash de integridad (`pnpm@x.y.z+sha512...`):
  aviso en desarrollo y **bloqueante en el empaquetado de release**
  (`package_release`). Con el hash, corepack verifica criptográficamente el
  binario de pnpm que descarga. Documentado en `docs/SECURITY.md` §13.
- **Pendiente al desplegar:** (1) generar `frontend/pnpm-lock.yaml` con
  `corepack pnpm import` (convierte `package-lock.json` preservando versiones
  exactas; después puede eliminarse `package-lock.json`); (2) fijar el hash de
  integridad con `corepack use pnpm@9.15.9` en `frontend/`. El empaquetado de
  release exige ambos.

### Eliminado

- `VALIDAR_MATRIX_RH.bat` e `INSTALAR_AUTOARRANQUE_MATRIX_RH.bat`. La lógica
  permanece disponible por PowerShell: `windows\Validate-MatrixRH.ps1` y
  `INSTALAR_MATRIX_RH.bat -WithAutostart` (o `windows\Install-Autostart.ps1`).
  Se actualizaron `package_release.py`, `preflight.py` y la documentación para
  eliminar referencias colgantes.

---

## [1.1.0] — 2026-08-12

Entrega funcional que amplía modelos, resumen de archivos, gobierno documental,
perfiles corporativos y frontend sin cambiar el contrato de API existente.

### Hotfix del instalador r1

- La comprobación de `uv 0.11.33` acepta tanto la salida corta como la salida
  oficial que incorpora hash y fecha de compilación antes del target Windows
  x64. Continúa rechazando otra versión, otra arquitectura, múltiples líneas o
  texto adicional.

### Añadido

- Intenciones separadas `identity`, `document_summary`, `documental`,
  `structured`, `mixed`, `conversational` y `general`.
- Contrato de identidad determinista: «¿quién eres?» responde exactamente
  `Soy Matrix RH.` sin invocar LLM ni RAG.
- Ruta de conocimiento general local para solicitudes fuera de RH, con prompt
  independiente que prohíbe presentar la respuesta como política interna.
- Resumen de adjuntos mediante `scroll` privado por metadata, con filtro Qdrant
  obligatorio `scope + owner_user_id + conversation_id`, sin embedding ni umbral
  semántico.
- Resumen jerárquico de documentos extensos: mapas Gemma en paralelo acotado,
  reduce Qwen, verificación de citas y fallback extractivo seguro.
- Presupuestos diferenciados: Gemma `8192/768` y Qwen `32768/2048`
  (`num_ctx/num_predict`), temperatura por intención, `keep_alive=15m` y caché
  LRU de embeddings con claves SHA-256.
- Árbol oficial `data/knowledge/general/**` y
  `data/knowledge/especializadas/<dominio>/**`, conservando compatibilidad con el
  corpus legacy sin moverlo automáticamente.
- Perfiles HCM corporativos acumulativos: `HCM_EMP_BASICO_MX` obligatorio más
  roles `HCM_ADM_*`/`HCM_COORD_*` por dominio.
- Dominios y grupos separados para Nómina General y Nómina Confidencial; los
  repositorios restringidos quedan fuera del wildcard.
- Sincronización Entra revocable: añade roles vigentes, retira los obsoletos y
  falla cerrado ante un especializado sin perfil base.
- Contrato Entra autocontenido con 19 roles y 19 mapeos, cargador idempotente y
  validación de categorías/permisos.
- Concesiones estructuradas corporativas explícitas: `hcm_adm_ia_matrix` sólo a
  `rh_demo`/`postgres_analytics` y `hcm_adm_admpersonal` sólo a
  `sap_hcm`/`oracle_hcm`; ningún coordinador recibe `structured.query`.
- Pruebas de regresión para identidad, routing, resumen privado/largo, límite de
  scan, perfiles HCM, revocación Entra, taxonomía y alcance administrativo.

### Cambiado

- El router usa Gemma por defecto y activa Qwen sólo por señales auditables de
  complejidad, contexto, herramientas o baja confianza.
- Las preguntas de RH y referencias documentales son fail-closed; una pregunta
  general ya no se fuerza a RAG por contener un signo de interrogación.
- La API administrativa publica en la ruta oficial y exige tanto
  `knowledge.admin` como categoría efectiva del rol. El resumen administrativo
  se filtra por el mismo alcance.
- Las categorías descubiertas quedan deny-by-default y fuera del wildcard hasta
  una política explícita.
- El frontend adopta la nueva presentación visual, accesos rápidos y trazabilidad
  de la respuesta actual conservando API, sesión, CSRF, cargas y chat.

### Corregido

- «Resume el archivo» ya no declara insuficiencia sólo porque la frase no se
  parece semánticamente al contenido cargado.
- Una falsa insuficiencia del modelo cuando existe evidencia legible se regenera
  y, como última red, produce un resumen extractivo citado.
- Un administrador funcional ya no puede publicar ni enumerar conocimiento de
  otro dominio.
- Retirar un grupo/app role de Entra ya no deja un rol interno obsoleto tras el
  siguiente login.

### Documentación

- Guías nuevas de perfiles de acceso, gobierno documental y operación rápida.
- README por carpeta para `general`, `especializadas`, sus nueve dominios, corpus
  legacy e infraestructura/pruebas que faltaban en diagnóstico.
- Instrucciones actualizadas de instalación, diagnóstico, Entra ID, resumen de
  adjuntos, rendimiento local y límites *document-grounded*, sin asignaciones
  personales de la matriz de acceso.
- Auditoría 1.1.0 separada de las cifras históricas: comprobaciones offline en
  `PASS` y gates Windows/MySQL/Qdrant/Ollama/E2E live pendientes del equipo
  destino, sin declarar una conexión no ejecutada.

---

## [1.0.3] — 2026-08-12

Segunda tanda de correcciones de instalación en equipo limpio. Todas salieron de
ejecuciones reales del `.bat` en la máquina destino, no de revisión de código: la
1.0.2 arreglaba el fallo del paso 7 pero introducía uno nuevo en el paso 3, y
esa versión nunca se había ejecutado desde cero.

### Corregido

- **DEF-019 — La comprobación de base se hacía antes de existir las dependencias.**
  El control de colisión añadido en la 1.0.2 vivía en el paso 3 y se apoya en
  SQLAlchemy dentro del `.venv`. En un equipo limpio ese venv aún está vacío, así
  que la instalación moría con `ModuleNotFoundError: No module named 'sqlalchemy'`.
  La comprobación pasa a ser el **paso 6**, después de "5/10 Dependencias de
  Python"; el instalador tiene ahora 10 pasos.
- **DEF-020 — El `ImportError` de la sonda escapaba como traceback.**
  Los `import` del Python incrustado en `Test-MatrixDatabaseFree` estaban en el
  nivel del módulo. Ahora van dentro de un `try` que emite el veredicto
  `DESCONOCIDO:SinDependencias`.
- **DEF-021 — Cualquier salida inesperada se interpretaba como "base ocupada".**
  El resultado se leía como "libre" sólo si era exactamente `LIBRE`; todo lo
  demás —incluido un mensaje de error— contaba como ocupada, y la búsqueda de
  nombre alternativo terminaba en `No se encontro un nombre de base libre`. Ahora
  el veredicto se valida contra una lista cerrada y un `DESCONOCIDO` descarta el
  candidato en lugar de reclamarlo.
- **DEF-022 — El diagnóstico reventaba sin `.venv`.**
  `DIAGNOSTICO_MATRIX_RH.bat` sobre un equipo sin instalar mostraba
  `ModuleNotFoundError: No module named 'pydantic'`. Ahora detecta la ausencia
  del entorno virtual, lo dice en una línea ("Matrix RH no esta instalado en este
  equipo"), comprueba lo único posible sin instalar —los puertos de MySQL y
  Ollama— y termina con `DIAGNOSTICO INCOMPLETO` y código 1.
- **DEF-024 — El quality gate declaraba herramientas "no instaladas" que sí lo estaban.**
  Dos causas, mismo síntoma. `npm` es `npm.cmd` y `CreateProcess` no ejecuta un
  `.cmd` sin intérprete, así que `subprocess` lanzaba `FileNotFoundError` y el
  gate lo traducía a `SKIPPED: herramienta no instalada`; en la práctica
  `npm audit`, Vitest y el build del frontend no se ejecutaban nunca desde el
  gate. Y `detect-secrets`, instalado como dependencia de desarrollo del propio
  proyecto, no aparecía porque el gate se invoca con la ruta absoluta del
  intérprete y la carpeta `Scripts` del venv no está en el `PATH`. Ahora las
  herramientas se buscan primero en el venv del proyecto y los `.cmd`/`.bat` se
  lanzan con `cmd /c`. Además `detect-secrets` excluye `.venv`, `node_modules`,
  `var` y `dist`, que no son código del proyecto y multiplicaban su duración.
  Un gate que se salta una comprobación y la llama "no instalada" miente sobre
  lo que ha verificado.
- **DEF-023 — Matrix RH adoptaba en silencio una base preexistente vacía.**
  Es el defecto de fondo, y el que explica el incidente del equipo destino. La
  guardia de la 1.0.2 sólo protegía bases *con tablas ajenas*; una base ajena que
  estuviera vacía —por ejemplo tras el `downgrade` de otro proyecto— se adoptaba
  sin avisar, y las dos aplicaciones acababan migrando sobre el mismo nombre.
  `ensure_database_exists()` devuelve ahora `(nombre, la_creamos_nosotros)` y
  `run_migrations` rechaza una base que ya existía y no tiene migraciones
  nuestras. El criterio pasa a ser **quién creó la base**, no qué contiene.

### Añadido

- `MATRIX_ADOPT_EXISTING_DATABASE` (por defecto `false`): permiso explícito para
  usar una base preexistente. Existe porque el caso legítimo —"esa base la creé
  yo para esto"— es real; lo que no puede pasar es que ocurra en silencio.
- Veredicto `EXISTE_VACIA` en el instalador, con su propio mensaje: la base
  existe, está vacía, y aun así Matrix RH elige otro nombre.
- 11 pruebas de adopción sobre bases temporales reales
  (`tests/integration/test_database_adoption.py`), incluida la que verifica que
  **rechazar la base no escribe nada dentro de ella**.
- 12 pruebas de mensajes al operador (`tests/unit/test_operator_messages.py`): que
  un error tipado sale como `ERROR [código] mensaje` y no como traceback, que los
  `.ps1` conservan las guardias (venv, `ErrorActionPreference`, veredictos
  cerrados, orden dependencias → base) y que el quality gate sabe lanzar `npm`.
- `TROUBLESHOOTING.md`: "La base X ya existía y no fue creada por Matrix RH" y
  "Quiero saber qué modifica mi base de datos" —con la activación de
  `general_log` y el `grep` verificable de que Matrix RH no contiene ningún
  `DROP TABLE` ni `DROP DATABASE`.

### Cambiado

- El ZIP de entrega ya no incluye `backend/.coverage` ni
  `frontend/tsconfig.tsbuildinfo`. Son cachés de herramientas y guardan rutas
  absolutas del equipo donde se generaron.

### Nota sobre el incidente del equipo destino

La base `matrix_rh` que aparecía y desaparecía con `alembic_version` y un `users`
de esquema desconocido pertenece a **otro proyecto Matrix RH** presente en la
misma máquina (`MatrixRH-1.1.2`), que usa Alembic y cuyo `downgrade()` elimina
las tablas en bucle. Matrix RH 1.0.x no contiene sentencias `DROP`. Con
`general_log` y `log_bin` en `OFF` no existe registro histórico que lo confirme
sentencia por sentencia; se documenta como lo que es, la explicación coherente
con el código de ambos proyectos.

---

## [1.0.2] — 2026-08-11

Correcciones encontradas al instalar el paquete en un equipo limpio
(`C:\wamp64\www\matrix-rh-1.0.1`). La instalación fallaba en el paso 7 con un
traceback ilegible.

### Corregido

- **DEF-015 — Consultar el estado ensuciaba una base ajena.**
  `pending_migrations()` creaba `schema_migrations` en la base configurada antes
  de que la guardia de propiedad pudiera actuar; es decir, contaminaba
  exactamente lo que pretendía proteger. Ahora `applied_versions()` sólo crea la
  tabla con `create=True`, y `run_migrations` la invoca **después** de verificar
  la propiedad. La verificación (`inspect_ownership`) es de solo lectura.
- **DEF-016 — El mensaje accionable se perdía en un traceback.**
  `scripts/bootstrap.py` captura los errores tipados y presenta
  `ERROR [código] mensaje` con la solución concreta, en lugar de dejar escapar la
  traza. Un operador que ejecuta un `.bat` no debe leer un stack de Python.
- **DEF-017 — PowerShell convertía stderr en `NativeCommandError`.**
  Cualquier escritura a stderr de un ejecutable nativo se envolvía como registro
  de error y sepultaba el mensaje real. `Invoke-MatrixPython` ahora fija
  `$ErrorActionPreference = 'Continue'` durante la llamada.
- **DEF-018 — El preflight reportaba un error genérico.**
  Ante una base de otra aplicación mostraba
  `usuarios_prueba: DatabaseUnavailableError`. Ahora hay una comprobación
  dedicada `base_de_datos_propia` que nombra la causa y la solución, y
  `usuarios_prueba` se degrada a aviso en vez de fallar por una dependencia no
  satisfecha.

### Añadido

- **Detección de colisión de base en el paso 3 del instalador**, no en el 7. Si
  la base configurada pertenece a otra aplicación, el instalador elige el primer
  nombre libre (`<base>_app`, `_app2`, …), lo escribe en `.env` y lo comunica de
  forma prominente. Es no destructivo: **nunca** toca la base ajena.
- Reconocimiento del estado `PROPIA`: reinstalar sobre una instalación previa de
  Matrix RH se detecta y se reutiliza, en lugar de tratarse como colisión.
- `Test-MatrixDatabaseFree` y `Set-MatrixEnvValue` en el helper de PowerShell.
- 11 pruebas de regresión (`tests/integration/test_database_ownership.py`) sobre
  bases temporales reales, incluida la que verifica que **la inspección no crea
  la tabla de control** y que la guardia no ensucia la base ajena.

### Verificado en el equipo destino

Instalación completa en `C:\wamp64\www\matrix-rh-1.0.1`: colisión detectada,
`.env` conmutado a `matrix_rh_app`, migraciones aplicadas, seed correcto,
`PREFLIGHT OK`, `/ready = true`, login de `MatrixR1` con acceso sólo a
`prestaciones`, interfaz servida con CSP. **La base `matrix_rh` del otro
proyecto quedó intacta** (`alembic_version` + `users`, sin `schema_migrations`).

---

## [1.0.1] — 2026-08-11

Endurecimiento de la cadena de suministro de npm, a raíz de un aviso sobre un
gusano autopropagable en el registro.

### Añadido

- `frontend/.npmrc` con `ignore-scripts=true`, `save-exact=true` y registro
  oficial forzado. **Es el control central**: aunque un paquete comprometido
  entre al árbol, su código no se ejecuta durante la instalación.
- `config/supply_chain_denylist.yaml` — lista de bloqueo de paquetes y versiones
  comprometidas, más los indicadores de compromiso a buscar. Es datos, no código.
- `scripts/verify_supply_chain.py` — verifica el árbol **realmente instalado**:
  lista de bloqueo a cualquier profundidad, scripts de instalación, indicadores
  de exfiltración y reproducibilidad (lockfile + `ignore-scripts`).
- 19 pruebas que construyen árboles sintéticos con un paquete comprometido, un
  `postinstall` y un IOC, y verifican que el control **dispara**.
- Gates `npm audit --omit=dev` (bloqueante) y `npm audit` completo (informativo)
  en el quality gate y en la validación.
- Comprobación de cadena de suministro en el preflight, en el instalador y en
  `VALIDAR_MATRIX_RH.bat`.

### Cambiado

- El instalador y el `Dockerfile` usan **`npm ci --ignore-scripts`** en lugar de
  `npm install`. El Dockerfile ya no cae a `npm install` si `npm ci` falla: una
  instalación no reproducible no debe llegar a una imagen.
- Dependencias de desarrollo actualizadas a versiones sin advisories:
  `vite` 6.0.7 → 8.2.1, `vitest` 2.1.8 → 4.1.10,
  `@vitejs/plugin-react` 4.3.4 → 6.0.5, `@playwright/test` 1.49.1 → 1.62.1,
  `@types/node` 22.10.5 → 22.20.1.
- `vite.config.ts` importa `defineConfig` de `vitest/config`: es la única que
  tipa la clave `test`.

### Corregido

- **`npm audit` pasó de 7 vulnerabilidades (1 critical, 3 high, 3 moderate) a 0.**
  Todas estaban en herramientas de desarrollo y ninguna viajaba en
  `frontend/dist`, pero el informe de auditoría inicial no las mencionaba.
- Tras la actualización, **ningún paquete del árbol declara scripts de
  instalación** (vite 8 ya no depende de `esbuild`), lo que elimina por completo
  el vector.

### Verificado

Auditoría del árbol instalado frente al aviso recibido: **ninguno** de los
paquetes señalados (`keyv`, `flat-cache`, `file-entry-cache`, `ecto`,
`cacheable-request`, `cacheable`, `cache-manager`, `@cacheable/*`) está presente
a ninguna profundidad. Esa familia entra normalmente vía ESLint, que este
proyecto no incluye. Sin indicadores de compromiso.

---

## [1.0.0] — 2026-08-11

Primera entrega completa.

### Añadido

**Plataforma**
- Backend FastAPI sobre Python 3.12 con configuración tipada y validada.
- Frontend React + TypeScript + Vite servido *same-origin*.
- Arranque por doble clic en Windows: instalación, arranque, detención,
  diagnóstico, validación y autoarranque opcional.
- `docker-compose.yml` y `Dockerfile` multi-stage con usuario no root.

**Identidad y autorización**
- Puerto `IdentityProvider` con adapters `local_test` y `entra`.
- OIDC Authorization Code + PKCE con patrón Backend-for-Frontend.
- Sesiones de servidor con cookie `HttpOnly` y SHA-256 del token en la base.
- `UserContext` inmutable y firmado con HMAC-SHA256.
- RBAC + ABAC con deny-by-default y wildcard resuelta a lista enumerada.
- Cuentas sintéticas `Matrix` y `MatrixR1` con hash Argon2id.

**RAG**
- Chunking estructural con frontera por encabezado.
- Qdrant en modo embebido o servidor, con filtros ACL dentro de la consulta.
- Recuperación `fetch_k` → dedup → MMR → `top_k` → diversidad por categoría.
- Verificador de grounding con allowlist de fuentes.
- Ingesta incremental por SHA-256 con reconciliación cada 24 h y lock.
- Extractores para `.docx`, `.md`, `.pdf`, `.txt`, `.xlsx` y `.csv` con límites
  anti-abuso.

**Agentes**
- Orquestador con orden autorizar → recuperar → validar → sintetizar → auditar.
- Agente de conocimiento sin acceso a herramientas de escalada.
- Política de dos modelos determinista y auditable.
- Planificador de consultas estructuradas a JSON validado.

**Datos estructurados**
- `StructuredQueryPlan` con `extra='forbid'`, validador de políticas, compilador
  parametrizado y verificación por AST.
- Adapters read-only para MySQL/MariaDB, PostgreSQL, SQL Server y Oracle.

**Seguridad**
- Redacción de secretos en el formatter de logging.
- Guard de cargas: allowlist, magic bytes, anti-zip-bomb, rutas seguras.
- Rate limiting por IP y por usuario.
- CSRF por token de sesión.
- CSP estricta y cabeceras de seguridad emitidas por el backend.
- Renderizador Markdown que construye nodos React (XSS imposible).

**Calidad**
- Suites unit, integración, seguridad, componentes y E2E Playwright.
- Golden set del RAG de 36 casos con métrica de fuga ACL.
- Quality gate único que coordina lint, typing, pruebas, SAST, dependencias,
  secretos, frontend, E2E y RAG.
- Escáner de secretos propio con supresiones auditables.

### Decisiones y correcciones durante la construcción

- **Prefijos de tarea de `embeddinggemma`.** Sin ellos, una pregunta legítima no
  recuperaba el párrafo que la respondía literalmente. Se añadieron
  `task: search result | query:` y `title: … | text: …`.
- **Encabezado como frontera de chunk.** Un documento corto entero caía en un
  solo chunk y su embedding quedaba diluido. El corpus pasó de 6 a 24 chunks y la
  mejor similitud subió de ~0.29 a 0.40–0.72.
- **Calibración del router.** Los marcadores de consulta estructurada incluían
  "cuántos"/"cuántas" a secas, lo que enviaba casi toda pregunta documental a la
  ruta profunda.
- **Escalada sólo por cobertura.** Un fallo de formato de cita se corrige con el
  mismo modelo rápido; escalar multiplicaba el coste sin mejorar la respuesta.
- **Protección contra bases ajenas.** El instalador se detiene si la base
  configurada ya contiene tablas de otra aplicación.
- **`trigger_source`.** `trigger` es palabra reservada en MySQL.
- **`utcnow_naive`.** MySQL `DATETIME` no guarda zona horaria; mezclar valores
  *aware* y *naive* rompía las comparaciones.
- **Validación de cargas antes de tocar infraestructura.** Un archivo rechazado
  devuelve 415/413 aunque el almacén vectorial esté caído.
- **Sesión por caso en la evaluación RAG.** Mantener una sola conexión abierta
  durante horas hacía que MySQL la cerrara.
- **`/etc/passwd` en rutas relativas.** Se comprobaba después de normalizar, lo
  que convertía una ruta absoluta en relativa aparentemente válida.

### Estado de integraciones

| Integración | Estado |
|---|---|
| Ollama (tres modelos) | `CONNECTED_AND_VALIDATED` |
| MySQL/MariaDB interna | `CONNECTED_AND_VALIDATED` |
| Qdrant embebido | `CONNECTED_AND_VALIDATED` |
| Microsoft Entra ID | `PREPARED_NOT_CONNECTED` |
| SQL Server / Oracle / PostgreSQL externos | `PREPARED_NOT_CONNECTED` |
