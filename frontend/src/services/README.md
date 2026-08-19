<!-- Creado por Aldo Garcia. -->

# frontend/src/services/

`api.ts` — cliente HTTP tipado.

## Decisiones de seguridad

- `credentials: "same-origin"`: la sesión viaja en una cookie `HttpOnly` que el
  JavaScript no puede leer.
- **Ningún token en `localStorage` ni `sessionStorage`.**
- El token CSRF se mantiene sólo en memoria del módulo y se envía en
  `X-CSRF-Token` en toda petición mutante.
- Los errores llegan tipados (`code`, `message`, `request_id`) y se exponen como
  `ApiError`; el frontend nunca muestra stack traces.
- `ChatReply` expone únicamente respuesta, fuentes ya autorizadas, intención,
  grounding y latencia. El panel visual no necesita un endpoint privilegiado.
