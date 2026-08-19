<!-- Creado por Aldo Garcia. -->

# data/knowledge/

Raíz del conocimiento corporativo oficial. La ruta determina la categoría que
se guarda en Qdrant y, por tanto, el filtro RBAC aplicado antes de recuperar
texto.

## Contrato de rutas

| Ruta | Categoría efectiva | Regla |
|---|---|---|
| `general/<tema>/<archivo>` | `general` | accesible con el perfil base concedido |
| `general/<archivo>` | `general` | igual; se recomienda subcarpeta de tema para orden documental |
| `especializadas/<dominio>/<archivo>` | `<dominio>` | requiere concesión explícita al dominio |
| `especializadas/<archivo>` | ninguna | se ignora y se registra aviso: falta el dominio |
| `<categoria>/<archivo>` | `<categoria>` | compatibilidad temporal con paquetes anteriores |
| `<archivo>` en esta raíz | ninguna | se ignora para evitar herencia accidental |

Para documentos nuevos use únicamente `general/` y `especializadas/`. El formato
anterior se conserva para actualizar una instalación sin reclasificar ni borrar
de forma automática el corpus existente.

## Dominios especializados iniciales

| Dominio | Grupos funcionales |
|---|---|
| `administracion_personal` | `HCM_ADM_ADMPERSONAL_MX`, `HCM_COORD_ADMPERSONAL_MX` |
| `nomina_general` | `HCM_ADM_NOMINA_GRAL_MX`, `HCM_COORD_NOMINA_GRAL_MX` |
| `nomina_confidencial` | `HCM_ADM_NOMINA_CONF_MX`, `HCM_COORD_NOMINA_CONF_MX` |
| `compensaciones` | `HCM_ADM_COMPENSACIONES_MX`, `HCM_COORD_COMPENSACIONES_MX` |
| `talento` | `HCM_ADM_TALENTO_MX`, `HCM_COORD_TALENTO_MX` |
| `reclutamiento` | `HCM_ADM_RECLUTAMIENTO_MX`, `HCM_COORD_RECLUTAMIENTO_MX` |
| `capacitacion` | `HCM_ADM_CAPACITACION_MX`, `HCM_COORD_CAPACITACION_MX` |
| `relaciones_laborales` | `HCM_ADM_RELLAB_MX`, `HCM_COORD_RELLAB_MX` |
| `matrix_rh_ia` | `HCM_ADM_IA_MATRIX_MX`, `HCM_COORD_IA_MATRIX_MX` |

`nomina_general` y `nomina_confidencial` son independientes. No coloque ambos
tipos de documento en `nomina/` ni conceda Confidencial mediante wildcard.

## Reglas de publicación

- Formatos: `.docx`, `.md`, `.pdf`, `.txt`, `.xlsx`, `.csv`.
- Los `README.md` se excluyen de la ingesta.
- Los archivos ocultos, extensiones no soportadas y rutas en la raíz se ignoran.
- Nombres de dominio: minúsculas, dígitos, `_` o `-`.
- Los slugs inseguros y los nombres reservados `general` o `especializadas`
  dentro del contenedor especializado se rechazan.
- Un dominio nuevo se descubre, pero queda deny-by-default y fuera del wildcard
  hasta declarar su política y concederlo a roles.
- Un archivo confidencial no se vuelve general porque su contenido lo afirme.
- Los adjuntos privados de chat no pertenecen a este árbol.

La actualización no mueve ni duplica automáticamente el corpus legacy. Sus
rutas siguen resolviendo la categoría anterior hasta una migración documental
controlada.

## Reconciliar

Desde la raíz del proyecto en `cmd.exe`:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.bootstrap ingest
```

La reconciliación automática corre según `RAG_REINDEX_INTERVAL_HOURS` (24 horas
por defecto) y detecta altas, cambios por SHA-256 y bajas. Para procedimiento y
pruebas de publicación consulte
[`docs/DOCUMENTATION_GOVERNANCE.md`](../../docs/DOCUMENTATION_GOVERNANCE.md).
