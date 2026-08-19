<!-- Creado por Aldo Garcia. -->

# Perfiles de acceso de Matrix RH

Este documento traduce la matriz funcional de perfiles v1.1 (Fase 1 y Fase 2)
a reglas técnicas. Se documentan grupos y decisiones; las asignaciones nominales
se mantienen fuera del repositorio para minimizar datos personales.

## Regla acumulativa

`HCM_EMP_BASICO_MX` es el perfil base obligatorio para toda persona con acceso a
Matrix RH. Un perfil especializado **se agrega** al perfil base; nunca lo
sustituye.

```text
acceso efectivo = HCM_EMP_BASICO_MX + cero o más grupos especializados
```

Una identidad con `HCM_ADM_*`, `HCM_COORD_*` o `HCM_COORD_CORE_*` pero sin
`HCM_EMP_BASICO_MX` debe fallar cerrado. La pertenencia a varios módulos es
válida y sus permisos se acumulan sin convertir un grupo de un módulo en
comodín para los demás.

## Convención y alcance

| Familia | Alcance funcional |
|---|---|
| `HCM_EMP_BASICO_MX` | Worker de Atención al Empleado y documentación del ámbito `general` |
| `HCM_ADM_<MODULO>_MX` | Consulta y administración documental sólo del módulo: carga, actualización y versionado |
| `HCM_COORD_<MODULO>_MX` | Consulta, supervisión funcional y reportes sólo del módulo |
| `HCM_COORD_CORE_<MODULO>_MX` | Alcance del módulo más las funciones transversales de Core HCM expresamente concedidas |
| `HCM_ADM_IA_MATRIX_MX` | Administración funcional de Matrix RH/IA, sin acceso implícito a secretos ni conversaciones ajenas |
| `HCM_COORD_IA_MATRIX_MX` | Coordinación funcional de Matrix RH/IA, sin privilegios administrativos implícitos |

Los módulos iniciales son Administración de Personal, Compensaciones, Talento,
Reclutamiento, Capacitación, Relaciones Laborales, Matrix RH/IA, Nómina General
y Nómina Confidencial. Incorporar un módulo nuevo exige una política explícita;
la ausencia de regla siempre significa `DENY`.

El contrato inicial versionado declara 19 roles/mapeos: el base y las parejas
Administrador/Coordinador de los nueve dominios. La familia `HCM_COORD_CORE_*`
procede de la matriz funcional, pero no tiene un mapeo genérico activo: cada
variante futura debe declarar categorías y permisos explícitos antes de usarse.

## Nómina General y Nómina Confidencial

Nómina no es un único alcance. Los grupos son independientes:

| Dominio | Administrador | Coordinador |
|---|---|---|
| Nómina General | `HCM_ADM_NOMINA_GRAL_MX` | `HCM_COORD_NOMINA_GRAL_MX` |
| Nómina Confidencial | `HCM_ADM_NOMINA_CONF_MX` | `HCM_COORD_NOMINA_CONF_MX` |

Tener acceso a Nómina General **no concede** acceso a Nómina Confidencial ni
permite inferir títulos, conteos, fragmentos o existencia de documentos de ese
repositorio. Nómina Confidencial requiere concesión nominal y no debe quedar
incluida en ningún comodín de negocio.

## Fuentes estructuradas

`structured.query` no basta por sí solo. El rol también necesita una
`StructuredSourcePermission` materializada desde los `allowed_roles` de
`config/data_sources/sources.yaml`:

| Rol corporativo | Permiso | Fuentes efectivas declaradas |
|---|---|---|
| `hcm_adm_ia_matrix` | `structured.query` | `rh_demo`, `postgres_analytics` |
| `hcm_adm_admpersonal` | `structured.query` | `sap_hcm`, `oracle_hcm` |
| cualquier `hcm_coord_*` | no concedido | ninguna |
| otros `hcm_adm_*` | no concedido | ninguna |

La fuente además debe estar habilitada y conectada con una cuenta read-only.
No existe herencia de conectores por wildcard ni por compartir `general`.

## Dónde se aplica

1. El proveedor de identidad obtiene los grupos corporativos durante el login.
2. El mapeo de grupos crea roles internos; un grupo no mapeado no concede nada.
3. `PolicyEngine` calcula categorías efectivas en cada request.
4. Qdrant recibe la lista concreta de categorías como parte de la consulta.
5. Los adjuntos privados se filtran por `user_id + conversation_id`, no por el
   rol corporativo.
6. La auditoría registra una huella del conjunto de roles, la decisión, fuentes
   y modelo, pero no copia el documento ni el prompt completo.

La integración corporativa está preparada en
`config/authorization/entra-role-mapping.yaml`. Mientras se usa
`AUTH_PROVIDER=local_test`, las cuentas sintéticas validan el contrato técnico,
pero **no sustituyen** la administración real de grupos del directorio.

## Criterios de aceptación

- Todo perfil especializado conserva el perfil base.
- Un usuario base recupera `general` y ningún módulo especializado.
- Un coordinador sólo consulta el módulo concedido.
- Un administrador sólo administra documentos de sus módulos.
- General y Confidencial de Nómina pasan pruebas positivas y negativas por
  separado.
- Ni el administrador puede abrir conversaciones privadas de otra persona.
- Revocar un grupo surte efecto en el siguiente login Entra; para un corte
  inmediato también se revocan las sesiones. La memoria previa que dependía de
  ese alcance deja de entrar al prompt.

Véanse también
[`AUTHENTICATION_AUTHORIZATION.md`](AUTHENTICATION_AUTHORIZATION.md) y
[`DOCUMENTATION_GOVERNANCE.md`](DOCUMENTATION_GOVERNANCE.md).
