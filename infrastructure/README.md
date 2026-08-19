<!-- Creado por Aldo Garcia. -->

# infrastructure/

Artefactos de despliegue.

| Carpeta | Contenido |
|---|---|
| `nginx/` | Reverse proxy con TLS y cabeceras de seguridad |
| `qdrant/` | Notas de operación del vector store |
| `database/` | Inicialización y usuarios de la base interna |

Sólo el proxy (`nginx`) se expone. MySQL y Qdrant escuchan en la red interna
`matrixrh` y no publican puertos. **Ollama no se conteneriza**: corre en el
host (los modelos pesan decenas de GB y usan la GPU), y el backend lo alcanza
por `host.docker.internal`.
