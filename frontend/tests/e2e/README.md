<!-- Creado por Aldo Garcia. -->

# frontend/tests/e2e/

Pruebas Playwright de los flujos completos contra FastAPI sirviendo el frontend
compilado en el mismo origen.

- Entradas: backend listo, corpus indexado y cuentas sintéticas de desarrollo.
- Salidas: resultados JSON, reporte HTML, trazas y capturas bajo las rutas
  configuradas en `playwright.config.ts`.
- Dependencias: árbol reproducible instalado con
  `npm ci --ignore-scripts` y navegador instalado con `npm run e2e:install`.

Ejecución desde `frontend/`:

```bat
npm run e2e
```

Los helpers centralizan autenticación y aserciones de no fuga. Ningún spec debe
desactivar autorización para hacer pasar un escenario. La cobertura y el mapa
de flujos están en [`../../../docs/E2E.md`](../../../docs/E2E.md).
