<!-- Registro de cambios derivados de la revision tecnica. -->

# Modificaciones del 7 de septiembre de 2026

## Cambios

- Se incorporo el `pnpm-lock.yaml` requerido por Docker e instaladores.
- Se fijo pnpm 9.15.9 con su integridad SHA-512 en `packageManager`.
- Docker y el harness usan `npm ci` para evitar fallos de claves obsoletas en
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
