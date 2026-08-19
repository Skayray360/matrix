<!-- Creado por Aldo Garcia. -->

# config/

Configuración declarativa. **Datos, nunca código**: todo se carga con
`yaml.safe_load` y se valida contra un esquema Pydantic. Un valor inesperado
impide el arranque.

| Carpeta | Contenido |
|---|---|
| `authorization/` | Políticas de categorías y mapeo de roles de Entra ID |
| `data_sources/` | Catálogo de fuentes estructuradas |

**Ningún archivo de esta carpeta contiene credenciales.**
