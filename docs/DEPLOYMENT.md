# Despliegue — Matrix RH

> Creado por Aldo Garcia.

---

## 1. Modos de despliegue

| Modo | Cuándo | Cómo |
|---|---|---|
| **Windows local (por defecto)** | Equipo de RH, piloto, demo | `INSTALAR_MATRIX_RH.bat` → `INICIAR_MATRIX_RH.bat` |
| **Windows con WAMP** | Ya existe WAMP en el equipo | Igual; WAMP provee MySQL y Apache puede actuar de proxy |
| **Contenedores** | Servidor Linux o Windows con Docker | `docker compose up -d` |

En los tres casos el núcleo es el mismo proceso Python 3.12 con FastAPI. **WAMP
no ejecuta el núcleo de IA**: puede proveer MySQL/MariaDB y servir el build del
frontend, pero el backend corre como proceso Python independiente y Ollama como
servicio local.

---

## 2. Instalación en Windows

Requisitos: Python 3.12 x64, Ollama con los tres modelos, MySQL/MariaDB,
opcionalmente Node.js para compilar la interfaz.

```bash
INSTALAR_MATRIX_RH.bat
```

El instalador detecta WAMP en `C:\wamp64\www` o `C:\wamp\www` y lo informa. La
ruta de instalación es configurable con `MATRIX_INSTALL_ROOT`; por defecto el
proyecto se opera desde donde se extrajo el ZIP.

**No sobrescribe una instalación existente**: conserva `.env`, reutiliza `.venv`
y las migraciones son idempotentes.

---

## 3. Contenedores

`docker-compose.yml` levanta MySQL, Qdrant, el backend y Nginx. Ollama se ejecuta
en el **host** (los modelos ocupan decenas de GB y suelen necesitar GPU), y el
backend lo alcanza por `host.docker.internal`.

```bash
docker compose up -d
```

Servicios:

| Servicio | Puerto interno | Expuesto |
|---|---|---|
| `nginx` | 80/443 | **sí** — único punto de entrada |
| `backend` | 8000 | no |
| `mysql` | 3306 | no |
| `qdrant` | 6333 | no |
| Ollama (host) | 11434 | no |

El backend corre como usuario **no root** dentro del contenedor.

---

## 4. Variables por entorno

| Variable | development | production |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `AUTH_PROVIDER` | `local_test` | `entra` |
| `LOCAL_TEST_AUTH_ENABLED` | `true` | **`false`** (el arranque falla si no) |
| `LOCAL_TEST_SEED_USERS_ENABLED` | `true` | **`false`** |
| `SESSION_COOKIE_SECURE` | `false` | **`true`** |
| `APP_SECRET_KEY` | autogenerada | **obligatoria**, desde el gestor de secretos |
| `APP_BASE_URL` | `http://127.0.0.1:8000` | URL pública HTTPS |
| `QDRANT_MODE` | `embedded` | `server` recomendado |

`Settings._validate_environment_safety` impide arrancar en producción con el
proveedor local, con el seed activo o sin cookie segura.

---

## 5. Checklist de producción

- [ ] `APP_ENV=production`
- [ ] `AUTH_PROVIDER=entra` con tenant, client y redirect URI reales
- [ ] `LOCAL_TEST_AUTH_ENABLED=false` y `LOCAL_TEST_SEED_USERS_ENABLED=false`
- [ ] Cuentas `Matrix` y `MatrixR1` **eliminadas o deshabilitadas**
- [ ] `APP_SECRET_KEY` desde el gestor de secretos, no en el repositorio
- [ ] `SESSION_COOKIE_SECURE=true` y TLS 1.2+ en el proxy
- [ ] Usuario de MySQL dedicado con permisos mínimos (no `root`)
- [ ] Usuarios **read-only** en cada fuente estructurada externa
- [ ] `QDRANT_MODE=server` con API key
- [ ] Ollama accesible sólo desde el backend
- [ ] Respaldo programado de la base interna
- [ ] `.env` fuera del repositorio y fuera del ZIP
- [ ] `windows\Validate-MatrixRH.ps1` ejecutado desde un entorno limpio

---

## 6. Reverse proxy

`infrastructure/nginx/matrixrh.conf` incluye TLS, cabeceras de seguridad, límite
de tamaño de cuerpo y proxy hacia el backend. Sólo el proxy es accesible desde
fuera; MySQL y Qdrant escuchan en la red interna. Ollama corre en el host (no se
conteneriza) y el backend lo alcanza por `host.docker.internal`.

---

## 7. Actualización

1. `DETENER_MATRIX_RH.bat`
2. Extraer la versión nueva conservando `.env` y `data/knowledge/`
3. `INSTALAR_MATRIX_RH.bat` (idempotente: sólo aplica lo que falta; al terminar
   arranca el sistema)
4. Si cambió `INGESTION_VERSION`, la ingesta reindexa automáticamente
5. `powershell -ExecutionPolicy Bypass -File windows\Validate-MatrixRH.ps1`

---

## 8. Autoarranque (opcional)

```bash
INSTALAR_MATRIX_RH.bat -WithAutostart
```

Registra una tarea programada **del usuario actual** (no requiere privilegios de
administrador) que arranca Matrix RH al iniciar sesión, sin abrir el navegador.
Para quitarla:

```bash
powershell -ExecutionPolicy Bypass -File windows\Install-Autostart.ps1 -Remove
```
