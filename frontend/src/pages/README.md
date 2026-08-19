<!-- Creado por Aldo Garcia. -->

# frontend/src/pages/

| Página | Contenido |
|---|---|
| `LoginPage` | Formulario local (development/test) y acceso corporativo Entra ID |
| `ChatPage` | Historial, identidad, accesos rápidos, conversación, trazabilidad y composer |

`LoginPage` muestra **tal cual** el mensaje del backend, que no distingue entre
usuario inexistente y contraseña incorrecta.

`ChatPage` es idéntica para `Matrix` y para `MatrixR1`. No hay ninguna opción
oculta por rol.

La pantalla conserva los contratos `/api/v1/me`, conversaciones, `/chat` y
adjuntos privados. Los accesos rápidos llaman a `sendMessage`; el panel de
trazabilidad se construye sólo con la última `ChatReply` y se limpia al abrir o
crear otra conversación.
