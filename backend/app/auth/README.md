<!-- Creado por Aldo Garcia. -->

# app/auth/

Autenticación: puerto `IdentityProvider` y sus adapters.

| Archivo | Contenido |
|---|---|
| `provider.py` | Puerto, `NormalizedIdentity`, `IntegrationStatus`, selector |
| `local_provider.py` | Proveedor de development/test contra la base interna |
| `entra_provider.py` | OIDC Authorization Code + PKCE, patrón BFF |
| `passwords.py` | Argon2id, verificación dummy en tiempo constante |
| `sessions.py` | Sesiones de servidor, cookies, CSRF |

## Regla que no se negocia

**No existe fallback automático.** Si Entra ID falla en producción, la petición
falla; nunca se cae al proveedor local. El proveedor local ni siquiera puede
instanciarse fuera de `development`/`test`.

## Qué se persiste

- De la contraseña: **sólo** el hash Argon2id.
- De la sesión: **sólo** el SHA-256 del token de cookie.
- Del token de Entra ID: **nada**. No sale del backend.
