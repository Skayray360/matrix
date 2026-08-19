<!-- Creado por Aldo Garcia. -->

# frontend/tests/

| Ruta | Suite |
|---|---|
| `Markdown.test.tsx` | Renderizado seguro: **XSS imposible**, citas verificadas, tablas |
| `Composer.test.tsx` | Envío con Enter, Shift+Enter, estado deshabilitado, adjuntos |
| `e2e/` | Playwright contra la pila real |
| `setup.ts` | Configuración de Vitest + Testing Library |

```bash
corepack pnpm test
```
```bash
corepack pnpm run e2e
```

Los E2E requieren el backend arriba. Instale Chromium una vez con
`corepack pnpm run e2e:install`. Ver `docs/E2E.md`.
