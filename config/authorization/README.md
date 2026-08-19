<!-- Creado por Aldo Garcia. -->

# config/authorization/

| Archivo | Contenido |
|---|---|
| `categories.yaml` | Taxonomía, sensibilidad, propietario, grupos permitidos y elegibilidad para wildcard |
| `entra-role-mapping.yaml` | Contrato de roles internos + grupos o app roles de Entra ID que los activan |

## Importante

Aparecer en `categories.yaml` **no concede acceso a nadie**. El acceso efectivo
se materializa en la base (`category_permissions`) por rol. El registro YAML
también permite validar la categoría y define sensibilidad, propietario y
elegibilidad para el comodín de negocio.

Una categoría con `wildcard_eligible: false` requiere concesión nominal incluso
para el administrador de negocio.

El modelo corporativo exige `HCM_EMP_BASICO_MX` más los grupos especializados
acumulativos. En particular, Nómina General y Nómina Confidencial usan grupos y
categorías independientes; Confidencial debe permanecer fuera de cualquier
wildcard. Véase [`docs/ACCESS_PROFILES.md`](../../docs/ACCESS_PROFILES.md).

El contrato distribuido usa valores de **app role** `HCM_*`. Si el tenant usa
grupos de seguridad, cambie cada `external_key` por su object ID real y
`external_kind` a `group`; no mezcle nombres visibles de grupos con object IDs.

El cargador valida el YAML y sincroniza de forma idempotente roles, categorías,
permisos y mapeos. Desde la raíz, primero revise sin escribir y después aplique:

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --dry-run
```

```bat
set "PYTHONPATH=%CD%\backend"
.venv\Scripts\python.exe -m scripts.load_entra_mapping --prune
```

`--prune` elimina de la tabla los mapeos que ya no están declarados. La
sincronización de login también retira roles Entra obsoletos. Un perfil
especializado sin el rol base `hcm_emp_basico` falla cerrado.
