<!-- Registro de cambios derivados de la revision tecnica. -->

# Modificaciones del 7 de septiembre de 2026

## Cambios

- Se consolido npm 10.9.0 como gestor canonico con `package-lock.json`.
- Docker, instaladores y harness usan `npm ci` para evitar fallos de claves obsoletas en
  versiones de Corepack distribuidas con algunos Node 22.
- Se sustituyo el healthcheck ficticio de Qdrant por una comprobacion TCP y el
  backend ahora espera `service_healthy`.
- Se agrego `MATRIX-DEV.ps1` con alias de setup, calidad, seguridad, Docker y
  generacion del paquete unificado.
- Se agregaron `npm run check` y `npm run ci`.
- Se ignoran los artefactos incrementales `*.tsbuildinfo`.
- Se documento estado, harness y estrategia de instalacion.

## Sin cambios

No se modificaron permisos, ACL, prompts, modelos, migraciones, datos ni la
restriccion de autenticacion local a desarrollo/pruebas.

## Limitaciones de validacion

El gate offline completo fue validado en este host con Python 3.12 administrado
por uv. La pila live requiere Docker Desktop activo y servicios/modelos locales.
Un gate omitido no equivale a aprobado.

## Correcciones posteriores al code review (8 de septiembre)

- npm quedo como unico gestor canonico; se retiro `pnpm-lock.yaml`.
- Empaquetador, supply-chain gate, quality gate, preflight, E2E y documentacion
  ahora consumen `package-lock.json`.
- El empaquetador falla si falta el lock realmente utilizado por `npm ci`.
- Se endurecio la prueba del paquete con script permitido para rechazar cualquier
  hallazgo adicional inesperado.
- Se agrego `.github/workflows/quality.yml` para ejecutar el gate en cada PR.
