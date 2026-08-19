<!-- Creado por Aldo Garcia. -->

# documentacion_empresarial/

Categoría efectiva: `documentacion_empresarial`.

| Nivel | Grupo |
|---|---|
| Administrador | `HCM_ADM_DOCEMPRESARIAL_MX` |
| Coordinador | `HCM_COORD_DOCEMPRESARIAL_MX` |

Dominio propio para documentación corporativa general de la empresa. Sensibilidad
`internal`, pero de acceso **nominal** (`wildcard_eligible: false`): no lo cubre el
comodín del administrador de negocio; sólo lo ve quien tenga su grupo/rol, además
de `HCM_EMP_BASICO_MX`.

Coloca aquí tus archivos (`.docx`, `.md`, `.pdf`, `.txt`, `.xlsx`, `.csv`). Este
`README.md` no se indexa. Tras copiar archivos, ejecuta la reconciliación
(`scripts.bootstrap ingest`).
