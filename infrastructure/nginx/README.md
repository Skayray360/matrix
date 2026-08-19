<!-- Creado por Aldo Garcia. -->

# infrastructure/nginx/

`matrixrh.conf` — reverse proxy de Matrix RH.

Aporta: terminación TLS (1.2 mínimo, 1.3 preferido), cabeceras de seguridad,
límite de tamaño de cuerpo, timeouts amplios para los turnos con el modelo
profundo y proxy hacia el backend.

Las cabeceras de seguridad se aplican **también** desde el backend, de modo que
el sistema sigue siendo seguro si se ejecuta sin proxy (arranque por doble clic).

## Certificados TLS

`docker-compose.yml` monta `infrastructure/nginx/certs/` en `/etc/nginx/certs`
(sólo lectura). Ese directorio **no se versiona**: los certificados dependen del
entorno y no deben viajar en el repositorio ni en el paquete. Antes del primer
`docker compose up` cree la carpeta y coloque el par de certificado y clave que
`matrixrh.conf` espera (o monte sus propios certificados corporativos). El
arranque por doble clic en Windows no usa este proxy y no requiere certificados.
