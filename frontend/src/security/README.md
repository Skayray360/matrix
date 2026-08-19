<!-- Creado por Aldo Garcia. -->

# frontend/src/security/

`Markdown.tsx` — renderizador de Markdown **seguro por construcción**.

En lugar de convertir Markdown a HTML y confiar en un sanitizador, construye
**elementos de React** directamente. No se usa `dangerouslySetInnerHTML`, por lo
que no existe ninguna vía por la que un documento corporativo o una respuesta del
modelo puedan inyectar HTML o script: un `<img onerror=...>` se muestra como
texto literal.

Además, una cita `[[source_id]]` que no esté en la lista de fuentes recibidas se
renderiza como texto plano, sin apariencia de fuente verificada. Es la última red
visual: el backend ya debería haberla rechazado.

Subconjunto soportado: encabezados, párrafos, listas, tablas, código en línea y
en bloque, negrita, cursiva y citas de Matrix RH.
