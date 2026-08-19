<!-- Creado por Aldo Garcia. -->

# app/authorization/

El `Authorization Guard` de la arquitectura.

| Archivo | Contenido |
|---|---|
| `context.py` | `UserContext` inmutable y firmado con HMAC-SHA256 |
| `policy.py` | Motor de decisiones RBAC + ABAC, deny-by-default |
| `categories.py` | Registro de categorías y su política declarativa |

## Las tres propiedades que hacen que esto funcione

1. El contexto se construye **una vez por request**, desde la sesión de servidor
   y la base de datos. Nunca desde datos del navegador.
2. Es **inmutable**: ninguna capa posterior puede ampliarlo.
3. Va **firmado**: un contexto fabricado o mutado por deserialización no pasa
   `verify()`.

## La wildcard

El rol administrativo de negocio tiene una concesión `is_wildcard`. El motor la
resuelve a una **lista enumerada** de categorías conocidas y elegibles: el filtro
que llega a Qdrant siempre es una lista concreta, nunca "sin filtro".

## Deny-by-default

La ausencia de una regla nunca concede acceso. Una categoría nueva descubierta en
disco se registra pero **no** se autoriza a nadie hasta que exista una regla
explícita.

## Perfiles corporativos

`HCM_EMP_BASICO_MX` es acumulativo y obligatorio. Los grupos `HCM_ADM_*` y
`HCM_COORD_*` agregan sólo el módulo concedido; no reemplazan el perfil base ni
se convierten en comodines. Nómina General y Nómina Confidencial se resuelven
como alcances independientes. La matriz sin asignaciones personales está en
[`docs/ACCESS_PROFILES.md`](../../../docs/ACCESS_PROFILES.md).
