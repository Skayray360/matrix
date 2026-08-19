<!-- Creado por Aldo Garcia. -->

# frontend/

Interfaz de Matrix RH: React 18 + TypeScript + Vite.

| Ruta | Contenido |
|---|---|
| `src/pages/` | `LoginPage`, `ChatPage` |
| `src/components/` | Conversaciones, mensajes, composer, accesos rápidos y panel de trazabilidad |
| `src/security/` | Renderizador Markdown seguro |
| `src/services/` | Cliente HTTP |
| `tests/` | Pruebas de componentes (Vitest) |
| `tests/e2e/` | Playwright |

## Comandos

El gestor oficial es **pnpm**, ejecutado por **corepack** (incluido en Node),
con la versión fijada en `packageManager` de `package.json`.

```bash
corepack pnpm install --frozen-lockfile --ignore-scripts
```
```bash
corepack pnpm run dev
```
```bash
corepack pnpm run build
```
```bash
corepack pnpm test
```
```bash
corepack pnpm run e2e
```

No use `npm install` ni `pnpm install` sin banderas: el proyecto exige el árbol
fijado por `pnpm-lock.yaml` (`--frozen-lockfile`) y bloquea los scripts de
instalación (`--ignore-scripts`). El ZIP incluye `frontend/dist`; Node.js sólo
es necesario si se va a recompilar o ejecutar las pruebas del frontend.

## Decisiones

- **Same-origin**: en desarrollo Vite hace proxy de `/api` al backend, para que la
  cookie `HttpOnly` + `SameSite` funcione igual que en producción.
- **Sin tokens en el navegador**: la sesión es una cookie que el JavaScript no
  puede leer. Nada en `localStorage` ni `sessionStorage`.
- **Sin `dangerouslySetInnerHTML`** en ninguna parte.
- **Misma interfaz para todos los roles**: la diferencia de información viene del
  backend. Ocultar un botón no es un control de seguridad.
- **Accesos rápidos sin privilegios**: cada tarjeta sólo envía un prompt normal;
  pasa por la misma intención, autorización, RAG y auditoría que el texto escrito.
- **Trazabilidad acotada**: el panel usa `intent`, `latency_ms`, `grounded` y las
  fuentes de la respuesta actual. No abre un endpoint administrativo ni muestra
  prompts, chunks, secretos o categorías no autorizadas.
- **Adjunto privado visible**: el composer distingue la carga de conversación
  del corpus corporativo; su ubicación visual no cambia el namespace técnico.

La actualización visual 1.1.0 conserva el cliente y los endpoints existentes:
`/me`, conversaciones, `/chat`, CSRF y carga privada. El build precompilado del
ZIP es el que sirve FastAPI en operación normal.
