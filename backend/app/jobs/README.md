<!-- Creado por Aldo Garcia. -->

# app/jobs/

Trabajos programados.

`scheduler.py` ejecuta la reconciliación del knowledge root cada
`RAG_REINDEX_INTERVAL_HOURS` (24 por defecto).

## Por qué un hilo y no una librería de scheduling

Es la única tarea periódica del sistema. Un hilo demonio con `Event.wait` es
interrumpible al apagar el proceso, no requiere dependencias y no introduce un
segundo modelo de concurrencia en el backend.

La protección frente a ejecuciones simultáneas **no vive aquí** sino en el lock
de base de datos, de modo que también cubre el caso de dos procesos distintos
(por ejemplo, el servidor y una ejecución manual del script).
