<!-- Estado verificado del repositorio Matrix RH. -->

# Estado actual de Matrix RH

Fecha de corte: 7 de septiembre de 2026. Base revisada: `main` en `94fa083`.

## Resumen ejecutivo

Matrix RH 1.1.0 es una aplicacion interna de Recursos Humanos diseñada para
ejecutarse localmente. Combina FastAPI, React, MySQL, Qdrant y Ollama. La
autorizacion y el filtrado documental se resuelven en el backend; la interfaz no
es una frontera de seguridad.

La base de codigo tiene una arquitectura clara y controles explicitos para
sesiones, CSRF, archivos, SQL de solo lectura, RAG con ACL y secretos. Antes de
esta revision, un clon limpio no podia completar el flujo oficial del frontend
porque faltaba `frontend/pnpm-lock.yaml`.

## Tecnologias y responsabilidades

| Capa | Tecnologia | Responsabilidad |
|---|---|---|
| Interfaz | React 18, TypeScript, Vite | Chat, autenticacion y fuentes |
| API | Python 3.12, FastAPI, Pydantic | Casos de uso y frontera HTTP |
| Persistencia | MySQL/MariaDB, SQLAlchemy | Usuarios, sesiones y auditoria |
| Recuperacion | Qdrant | Vectores con filtros ACL |
| IA local | Ollama | Embeddings y generacion local |
| Identidad | Local de prueba / Entra ID | Autenticacion y roles |
| Operacion | PowerShell, Bash, Docker Compose | Instalacion y despliegue |

## Evidencia de esta revision

| Validacion | Resultado |
|---|---|
| Vitest | 14/14 aprobadas |
| TypeScript + Vite | Build de produccion aprobado |
| Auditoria npm | 0 vulnerabilidades |
| Backend offline | 473 aprobadas, 36 omitidas por dependencias live |
| Ruff | Aprobado |
| mypy | Aprobado en 82 archivos fuente |
| Escaneo de secretos | Aprobado, 0 secretos reales |
| Cadena de suministro | Aprobada, 149 manifiestos revisados |
| Docker runtime | No ejecutado: Docker Desktop no estaba iniciado |

El reporte historico `reports/RELEASE_VALIDATION_1.1.0.md` declara 495 pruebas
backend en su entorno. Esta revision valido el subconjunto offline y de seguridad;
los 36 casos live permanecen pendientes del entorno operacional.

## Riesgos y pendientes

1. La validacion integral requiere MySQL, Ollama y sus tres modelos, y Qdrant
   cuando se usa en modo servidor.
2. Las imagenes Docker usan etiquetas versionadas, pero no digests inmutables.
3. El rate limit en memoria presupone una sola replica del backend.
4. La huella opcional del cliente existe en sesiones, pero no forma parte de una
   politica activa de deteccion o rechazo.
5. Entra ID requiere validacion con el tenant real del equipo destino.

## Criterio de listo

```powershell
.\MATRIX-DEV.ps1 check
.\MATRIX-DEV.ps1 validate
.\MATRIX-DEV.ps1 docker-config
```

`check` cubre calidad offline; `validate`, la pila local; `docker-config`, la
composicion sin desplegarla.
