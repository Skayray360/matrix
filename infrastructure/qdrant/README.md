<!-- Creado por Aldo Garcia. -->

# infrastructure/qdrant/

Notas de operación del almacén vectorial.

## Dos modos

| Modo | Cuándo | Limitación |
|---|---|---|
| `embedded` | Equipo Windows sin Docker (por defecto) | **Un solo proceso** puede abrir el almacén |
| `server` | Servidor o contenedor | Ninguna; recomendado en producción |

## Respaldo

El índice **no requiere respaldo**: se reconstruye desde `data/knowledge/` con

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap ingest
```

## Si el índice se corrompe

Detener el backend, conservar el corpus oficial, retirar el índice dañado de
`var/qdrant/` mediante el procedimiento de respaldo de su organización y
reindexar. El borrado del índice no debe ejecutarse con el backend abierto.
