<!-- Creado por Aldo Garcia. -->

# frontend/src/components/

| Componente | Papel |
|---|---|
| `Sidebar` | Lista de conversaciones propias, crear y eliminar |
| `MessageList` | Turnos con sus fuentes citadas y estados de carga |
| `Composer` | Texto + adjuntos con drag & drop |
| `QuickActions` | Temas visuales que envían prompts ordinarios, sin conceder acceso |
| `TracePanel` | Metadata autorizada de la última respuesta: intención, latencia y fuentes |

## Accesibilidad

Etiquetas y ARIA en todos los controles, navegación por teclado, foco visible,
`aria-live` en la conversación y estados *loading* / *empty* / *error* explícitos.

## Detalle que importa

`Composer` dice explícitamente que el adjunto se analiza **sólo en esa
conversación**. Confundir un adjunto privado con conocimiento corporativo es la
forma más fácil de publicar por accidente un documento personal.

`TracePanel` no reconstruye una traza interna ni consulta auditoría global. Se
reinicia al cambiar de conversación y sólo recibe campos que ya devolvió `/chat`.
`QuickActions` no contiene categorías confiables ni salta el router: el backend
vuelve a clasificar y autorizar su prompt.
