<!-- Creado por Aldo Garcia. -->

# app/common/

Utilidades transversales. **No dependen de ningún otro paquete del proyecto.**

| Archivo | Contenido |
|---|---|
| `errors.py` | Catálogo cerrado de errores tipados con su código y HTTP status |
| `logging.py` | Formatter JSON que redacta antes de escribir |
| `redaction.py` | Patrones de secretos y redacción recursiva |
| `ids.py` | UUID opacos, tokens seguros, SHA-256, `utcnow_naive` |

## Dos decisiones que conviene conocer

**La redacción vive en el formatter, no en el llamador.** Así es imposible
filtrar un secreto por un `logger.info` descuidado.

**`utcnow_naive()` para todo lo que se persiste.** MySQL `DATETIME` no almacena
zona horaria; si se guardaran valores *timezone-aware*, al releerlos vendrían
naive y cualquier comparación en Python (`expires_at < now`) fallaría. El
criterio único es "naive == UTC".
