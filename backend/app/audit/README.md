<!-- Creado por Aldo Garcia. -->

# app/audit/

Servicio de auditoría.

Registra: identidad opaca, hash del conjunto de roles, conversación, intención,
modelo seleccionado, herramientas usadas, `source_ids` citados, decisión de
autorización, latencia, estado y código de error.

**No registra**: contraseñas, client secrets, bearer tokens, llaves privadas,
documentos completos ni prompts completos. Del contenido sólo se guardan
identificadores de fuente, nunca el texto recuperado.

Cada evento se escribe en la misma transacción del request, de modo que no puede
haber una respuesta entregada sin su registro correspondiente.
