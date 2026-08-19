<!-- Creado por Aldo Garcia. -->

# especializadas/

Contenedor de repositorios documentales por dominio. No es una categoría por sí
mismo: un archivo colocado directamente aquí se ignora y produce un aviso.

```text
especializadas/<dominio>/<archivo>
```

La categoría efectiva es `<dominio>`. Un dominio nuevo queda deny-by-default y
fuera del wildcard hasta declarar su política y conceder sus grupos/roles. Los
`README.md` no se indexan.

Nómina General y Nómina Confidencial están segregadas físicamente; nunca se
fusionan en una carpeta `nomina` común.
