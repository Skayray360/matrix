# Solución de problemas — Matrix RH

> Creado por Aldo Garcia.

Primer paso siempre:

```bash
DIAGNOSTICO_MATRIX_RH.bat
```

No modifica nada y dice exactamente qué componente falla.

---

## 1. Instalación

### "Se requiere Python 3.12 (encontrado 3.13)"

Matrix RH se valida contra 3.12. Instale Python 3.12 x64 y vuelva a ejecutar; el
instalador usa `py -3.12` si el lanzador está disponible.

### "Faltan modelos en Ollama"

```bash
ollama pull gemma4:latest
```
```bash
ollama pull qwen3.6:latest
```
```bash
ollama pull embeddinggemma:latest
```

### "La dimension real de embeddinggemma es N y se esperaba 768"

Matrix RH **no trunca ni rellena vectores**. Si el modelo cambió de dimensión, hay
que ajustar `RAG_EMBEDDING_DIMENSION` y `OLLAMA_EMBEDDING_DIMENSION` **y
reindexar por completo**; un índice con dimensiones mezcladas es inservible.

### "La base de datos configurada ya contiene tablas de otra aplicación"

Protección deliberada: Matrix RH **no escribe sobre una base ajena**.

Desde la versión 1.0.3 el instalador lo detecta en el **paso 6** —
inmediatamente después de instalar las dependencias de Python, porque la
comprobación se hace con SQLAlchemy y antes del paso 5 el entorno virtual aún
está vacío— y lo resuelve solo: elige el primer nombre libre (`<base>_app`,
`_app2`, …), lo escribe en `.env` y lo anuncia. Verá algo así:

```text
[WARN] La base 'matrix_rh' YA EXISTE y contiene tablas de otra aplicacion:
       alembic_version,users
       Matrix RH no va a modificarla.
[ OK ] Matrix RH usara la base 'matrix_rh_app' (escrito en .env).
       Su base 'matrix_rh' queda intacta.
```

Si prefiere otro nombre, edite `DATABASE_URL` en `.env` antes de reinstalar.

Ejecutando un comando suelto (no el instalador) verá el mensaje accionable
directamente:

```text
ERROR [configuration_error] La base de datos configurada ya contiene tablas de
otra aplicacion (alembic_version, users). Matrix RH no la va a modificar.
         Solucion: edite DATABASE_URL en .env y use un nombre libre, por
         ejemplo matrix_rh_app.
```

> Reinstalar sobre una base creada por **Matrix RH** no es una colisión: se
> detecta como `PROPIA` y se reutiliza.

### "La base X ya existía y no fue creada por Matrix RH"

```text
ERROR [configuration_error] La base 'matrix_rh' ya existia y no fue creada por
Matrix RH.
         Matrix RH no adopta bases preexistentes por si pertenecen a
         otra aplicacion, aunque ahora esten vacias.
         Opciones: (a) use un nombre nuevo en DATABASE_URL y deje que
         Matrix RH la cree, o (b) si esta base es suya y la quiere usar,
         ponga MATRIX_ADOPT_EXISTING_DATABASE=true en .env.
```

Es distinto del caso anterior: aquí la base **está vacía**. Aun así Matrix RH no
la usa, porque "vacía" y "libre" no son lo mismo. El caso real que motivó este
control: en el equipo destino existía una base `matrix_rh` de otro proyecto que
gestionaba su esquema con Alembic; un `downgrade` la había dejado sin tablas.
Adoptarla habría puesto a dos aplicaciones a migrar sobre el mismo sitio.

El criterio no es qué hay dentro, sino **quién creó la base**. Si Matrix RH la
creó, o si ya tiene migraciones suyas registradas en `schema_migrations`, la usa
sin preguntar.

Las dos salidas:

- **Recomendada** — deje que Matrix RH cree la suya. Edite `DATABASE_URL` en
  `.env` con un nombre que no exista (por ejemplo `matrix_rh_hr`). El instalador
  hace esto por usted automáticamente.
- **Si la base es suya y la quiere reutilizar** — añada a `.env`:

```text
MATRIX_ADOPT_EXISTING_DATABASE=true
```

Sólo afecta al primer arranque: una vez aplicadas las migraciones, la base pasa
a ser de Matrix RH y la bandera deja de tener efecto.

### "Quiero saber qué modifica mi base de datos"

Matrix RH **no contiene ninguna sentencia `DROP TABLE` ni `DROP DATABASE`** en
código de aplicación ni en migraciones. Puede comprobarlo usted mismo sobre el
paquete que le entregamos:

```bash
grep -rn "DROP TABLE\|DROP DATABASE" backend/app backend/migrations
```

(Los únicos `DROP` del repositorio están en pruebas de integración, sobre bases
temporales con nombre aleatorio `matrix_rh_test_*` / `matrix_rh_adopt_*` que
ellas mismas crean.)

Si sospecha que **otra** aplicación está tocando su base, MySQL puede decírselo,
pero sólo a partir del momento en que active el registro — no hay forma de
reconstruir lo que pasó antes:

```sql
SET GLOBAL general_log_file = 'C:/wamp64/logs/general.log';
```
```sql
SET GLOBAL general_log = 'ON';
```

Deja constancia de **todas** las sentencias de **todos** los clientes, con su
usuario y host. Crece rápido: actívelo mientras investiga y apáguelo después con
`SET GLOBAL general_log = 'OFF';`. Para saber si estaba activo antes:

```sql
SHOW VARIABLES LIKE 'general_log%';
```
```sql
SHOW VARIABLES LIKE 'log_bin';
```

Con ambos en `OFF` no existe registro histórico de quién modificó qué.

### La instalación falla con "Traceback (most recent call last)"

Ocurría en versiones anteriores a la 1.0.2: PowerShell convertía la salida de
error de Python en un `NativeCommandError` y el mensaje real quedaba sepultado.
Corregido. Si aún lo ve, ejecute el comando directamente para leer el motivo:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap migrate
```

(desde la raíz del proyecto).

### `ModuleNotFoundError: No module named 'sqlalchemy'` durante la instalación

Defecto de la 1.0.2, corregido en la 1.0.3. La comprobación de colisión de base
estaba en el **paso 3**, antes de que se instalaran las dependencias, así que en
un equipo limpio moría al importar SQLAlchemy y a continuación anunciaba
`No se encontro un nombre de base libre`. Ahora la comprobación es el **paso 6**,
después del paso 5 (dependencias), y si aun así no puede ejecutarse informa
`DESCONOCIDO` y continúa en lugar de dar por ocupada la base.

### `ModuleNotFoundError: No module named 'pydantic'` al ejecutar el diagnóstico

Defecto de la 1.0.2, corregido en la 1.0.3. Si el diagnóstico se ejecuta antes
de instalar, no hay `.venv` y el preflight no puede importar el backend. Ahora
lo dice en una línea:

```text
[FAIL] Matrix RH no esta instalado en este equipo: falta el entorno virtual (.venv).
       Ejecute INSTALAR_MATRIX_RH.bat y repita el diagnostico despues.
```

y comprueba lo único que sí puede sin instalar: que MySQL (3306) y Ollama
(11434) estén escuchando.

### El preflight dice `usuarios_prueba: DatabaseUnavailableError`

Síntoma de la versión 1.0.1 cuando la base pertenecía a otra aplicación: el
error real quedaba oculto tras un fallo derivado. Desde la 1.0.2 el preflight
muestra la causa en la comprobación `base_de_datos_propia` y degrada
`usuarios_prueba` a aviso.

### "Las migraciones fallaron"

Compruebe que MySQL está arriba (`DIAGNOSTICO_MATRIX_RH.bat`) y que el usuario de
`DATABASE_URL` puede crear bases y tablas. Con WAMP, el servicio MySQL debe estar
en verde.

---

## 2. Arranque

### El backend no responde a `/health`

Revise las últimas líneas del log de errores que indica el propio script
(`var/logs/backend-*.err.log`). Causas frecuentes: puerto 8000 ocupado por otro
proceso, `.env` con un valor inválido, MySQL caído.

### `/ready` devuelve `false`

`DIAGNOSTICO_MATRIX_RH.bat` lista qué componente está mal. La semántica es
deliberada: el proceso está vivo pero una dependencia obligatoria no lo está, y
el sistema **no** se declara listo.

### "El almacen embebido admite un unico proceso"

Con `QDRANT_MODE=embedded`, el índice queda bloqueado por el proceso que lo abre.
Detenga el backend antes de ejecutar scripts que accedan directamente al índice:

```bash
DETENER_MATRIX_RH.bat
```

O use `QDRANT_MODE=server` con una instancia Qdrant dedicada.

### "El puerto está ocupado por otro proceso"

Cambie `APP_PORT` en `.env` o libere el puerto. Si lo ocupa Matrix RH, el
diagnóstico lo identifica como tal.

---

## 3. Uso

### "No cuento con información documental suficiente" para algo que sí está documentado

1. ¿El documento oficial está bajo `data/knowledge/general/<tema>/` o
   `data/knowledge/especializadas/<dominio>/`?
2. ¿Se indexó? Ejecute desde la raíz:

   ```bat
   set "PYTHONPATH=%CD%\backend"
   .venv\Scripts\python.exe -m scripts.bootstrap ingest
   ```

   Después revise `documents.status`.
3. ¿El usuario tiene el ámbito efectivo? Consulte `/api/v1/me`; un grupo
   especializado no sustituye `HCM_EMP_BASICO_MX`.
4. ¿El formato es soportado? Un PDF escaneado sin OCR no aporta texto: el
   documento queda en estado `empty` con un aviso explícito.
5. ¿El archivo está en Nómina General o Confidencial? Verifique el grupo exacto;
   son repositorios independientes.

### Un archivo adjunto está `indexed`, pero «Resume el archivo» declara insuficiencia

1. Confirme que pregunta en **la misma conversación** donde subió el archivo.
2. Espere el estado `indexed`; `pending`, `empty` o `failed` no aportan evidencia.
3. Pida explícitamente «Resume el archivo adjunto» o «Sintetiza sus puntos clave».
   Esa intención recupera por metadata y no depende de similitud semántica.
4. Revise el evento `rag.private_summary_retrieved`: debe registrar chunks para
   el `owner_user_id + conversation_id` actuales, sin exponer su contenido.
5. Revise `error_message` del documento y las advertencias de extracción. Un
   archivo puede estar indexado parcialmente (por ejemplo, páginas PDF sin
   capa de texto).

Sin evidencia privada recuperada Matrix RH no llama al modelo para inventar un
resumen. Si hay varios adjuntos, la ruta resume el contenido privado disponible
en la conversación completa; cree una conversación separada para aislar uno. No
copie el archivo al corpus corporativo para sortear este diagnóstico.

Si la respuesta incluye la nota de límite, el adjunto superó
`RAG_SUMMARY_SCAN_MAX_CHUNKS` y el resumen cubre sólo el material procesado. No
aumente el límite sin medir memoria, contexto y tiempo de ejecución.

### "No tiene acceso a esa información" con el usuario correcto

Consulte `allowed_categories` en `/api/v1/me`. Si falta la categoría, hace falta
una regla explícita en `category_permissions` — **deny-by-default** es el
comportamiento diseñado, no un error.

### La respuesta tarda varios minutos

Compruebe el campo `model` de la respuesta o el evento `chat.answer`. Una
comparación, consulta larga, flujo multiherramienta o cobertura difícil puede
usar la ruta profunda. Si el modelo no cabe entero en GPU, Ollama lo ejecuta
parcialmente en CPU. Verifíquelo con:

```bash
ollama ps
```

Una columna `PROCESSOR` que combine CPU/GPU explica gran parte de la latencia.
`OLLAMA_KEEP_ALIVE=15m`, la caché acotada de embeddings y Gemma como ruta normal
ya reducen trabajo repetido. No reduzca ACL ni verificación de citas para
acelerar: use las métricas de `chat.answer`, confirme qué señal activó Qwen y
ajuste sólo los parámetros documentados de Ollama/RAG.

### Una pregunta general recibe respuesta documental o viceversa

La intención documental se activa con referencias a archivos/fuentes y con
vocabulario de RH (política, vacaciones, nómina, salario, reclutamiento, etc.).
Eso es fail-closed: evita convertir conocimiento general en una política interna.
Formule una consulta general sin atribuirla a la empresa. Si una pregunta de RH
entra como general, conserve el `request_id` y reporte la frase exacta sin datos
sensibles para ampliar los marcadores y su prueba de regresión.

### Un documento subido queda en estado `failed`

El motivo está en `error_message` (visible en `/api/v1/documents/{id}/status`).
Causas típicas: archivo protegido con contraseña, OOXML corrupto, o el contenido
no corresponde a la extensión declarada.

### Preguntar «¿quién eres?» no responde «Soy Matrix RH»

La identidad es un contrato independiente del modelo. Reinicie el backend para
cargar la versión actual y compruebe que no haya otro proceso escuchando en el
puerto configurado. Si persiste, registre el `request_id` y el campo `model`; no
modifique prompts ni archivos del corpus para corregir identidad.

---

## 4. Seguridad

### "Token CSRF invalido o ausente"

El frontend obtiene el token en `/api/v1/me` y lo envía en `X-CSRF-Token`. Si
llamas a la API con una herramienta externa, incluye la cabecera. Un token de
otra sesión no sirve: es el comportamiento correcto.

### "Cuenta bloqueada temporalmente por intentos fallidos"

Cinco intentos fallidos consecutivos bloquean la cuenta 5 minutos. Espere o
reinicie el backend (el bloqueo vive en `local_credentials.locked_until`).

### El escáner de secretos marca un fixture de prueba

Añada un marcador con justificación en la línea o en la anterior:

```python
# secrets-scan: allow (JWT sintetico sin firma valida, fixture de redaccion)
```

Todas las supresiones se publican en `reports/security/secrets_scan.json` para
que puedan revisarse una por una.

---

## 5. Recuperación

| Situación | Acción |
|---|---|
| Índice vectorial corrupto | Borrar `var/qdrant/` y ejecutar `scripts.bootstrap ingest` |
| Base interna corrupta | Restaurar el `mysqldump` y ejecutar `scripts.bootstrap migrate` |
| `APP_SECRET_KEY` rotada | Todas las sesiones se invalidan; los usuarios vuelven a entrar |
| Reconciliación colgada | El lock expira a los 60 min; para forzar, borrar la fila de `job_locks` |
| Instalación inconsistente | Borrar `.venv/` y `var/`, conservar `.env` y `data/knowledge/`, reinstalar |

---

## 6. Dónde mirar

| Qué | Dónde |
|---|---|
| Logs del backend | `var/logs/backend-*.log` y `*.err.log` |
| Evento concreto | `audit_events` filtrando por `request_id` (aparece en la respuesta de error y en la cabecera `X-Request-ID`) |
| Estado de documentos | Tabla `documents` |
| Ejecuciones de reconciliación | Tabla `ingestion_jobs` |
| Parámetros efectivos | `GET /api/v1/admin/diagnostics` |
| Evidencia de la última validación | `reports/final-validation.json` |
