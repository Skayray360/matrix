<!-- Guia del harness de desarrollo de Matrix RH. -->

# Harness de desarrollo y alias

`MATRIX-DEV.ps1` ofrece una entrada estable a las herramientas del proyecto y
configura directorios y `PYTHONPATH` de forma consistente.

## Requisitos

- PowerShell 7 o Windows PowerShell 5.1.
- Python 3.12 x64 y `uv` para el backend.
- Node.js 22 LTS y npm para el frontend.
- Docker Desktop para los comandos Docker.
- Los servicios de `OPERATOR_QUICKSTART.md` para `validate`.

## Alias

| Alias | Tecnologia | Uso |
|---|---|---|
| `setup`, `install`, `bootstrap` | uv + npm | Instala los locks sin scripts npm |
| `check`, `ci` | Todas | Gate offline antes de un commit |
| `test` | pytest + Vitest | Pruebas offline |
| `backend-test`, `frontend-test` | pytest / Vitest | Pruebas por capa |
| `lint` | Ruff | Calidad Python |
| `typecheck` | mypy + TypeScript | Contratos de tipos |
| `build` | Vite | Bundle de produccion |
| `security` | Scanners + npm audit | Secretos y dependencias |
| `validate` | Harness operacional | Pila completa y evidencia JSON |
| `package` | Empaquetador Python | ZIP unificado de entrega |
| `docker-config` | Docker Compose | Sintaxis e interpolacion |

```powershell
.\MATRIX-DEV.ps1 setup
.\MATRIX-DEV.ps1 check
.\MATRIX-DEV.ps1 package
```

El frontend tambien expone `npm run check` y `npm run ci`.

## Locks y Corepack

Docker y los instaladores existentes usan pnpm 9.15.9 con hash de integridad. El
harness usa `npm ci`, disponible con Node, y evita depender de Corepack para el
gate diario. Ambos locks se mantienen versionados y
deben actualizarse juntos cuando cambie `package.json`:

```powershell
cd frontend
npm install --package-lock-only --ignore-scripts
npx --yes pnpm@9.15.9 install --lockfile-only --ignore-scripts
```
