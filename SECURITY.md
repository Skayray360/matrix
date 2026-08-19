# Política de seguridad — Matrix RH

> Creado por Aldo Garcia.

---

## Reportar una vulnerabilidad

Matrix RH es un sistema interno. Si encuentra una vulnerabilidad:

1. **No la publique** en canales abiertos ni en tickets accesibles a toda la
   organización.
2. Contacte al responsable del proyecto por el canal interno de seguridad.
3. Incluya: componente afectado, versión, pasos de reproducción, impacto
   estimado y, si es posible, una prueba automatizada que falle.
4. No use datos reales de empleados para demostrar el hallazgo. El corpus
   sintético del repositorio es suficiente.

Compromiso de respuesta: acuse en 2 días hábiles, evaluación de severidad en 5.

---

## Alcance

**Dentro del alcance**: backend, frontend, scripts de instalación, configuración
declarativa, controles de autorización, manejo de secretos, ingesta y agentes.

**Fuera del alcance**: vulnerabilidades de Ollama, MySQL, Qdrant o Nginx como
productos (repórtelas a sus proyectos), y hallazgos que requieran acceso físico o
privilegios de administrador del sistema operativo.

---

## Severidades y compromiso

| Severidad | Ejemplo | Compromiso |
|---|---|---|
| **Crítica** | Fuga de datos entre roles, bypass de autenticación, RCE | Corrección inmediata; bloquea la entrega |
| **Alta** | IDOR, escalada de privilegios, exposición de secretos | Corrección antes de la siguiente entrega |
| **Media** | Falta de rate limiting en una ruta, cabecera ausente | Corrección o mitigación documentada con aprobación |
| **Baja** | Mensaje de error demasiado descriptivo | Backlog priorizado |

Criterio de entrega: **cero** vulnerabilidades críticas y altas abiertas.

---

## Credenciales sintéticas

Las cuentas `Matrix` y `MatrixR1` con contraseña `Matrix RH` son **credenciales
sintéticas de prueba declaradas en la especificación**, no secretos productivos.

- Sólo funcionan con `APP_ENV=development` o `test`.
- La base almacena únicamente un hash Argon2id.
- El arranque con `APP_ENV=production` **falla** si el proveedor local o el seed
  siguen habilitados.
- Deben eliminarse o deshabilitarse antes de producción
  (ver `docs/integrations/MIGRATE_LOCAL_TEST_TO_ENTRA.md`, Fase 5).

Encontrarlas en el repositorio **no es un hallazgo de seguridad**.

---

## Controles que puede verificar usted mismo

```bash
python -m scripts.secrets_scan --allow-env
```
```bash
python -m pytest tests/security -q
```
```bash
python -m bandit -q -r app -x tests
```
```bash
python -m pip_audit --strict
```
```bash
powershell -ExecutionPolicy Bypass -File windows\Validate-MatrixRH.ps1
```

Documentación de referencia: [`docs/SECURITY.md`](docs/SECURITY.md) y
[`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

---

## Supresiones

Toda supresión de un hallazgo requiere justificación específica en el propio
código:

```python
# secrets-scan: allow (motivo concreto)
```
```python
# noqa: S105  # nosec B608
```

Las supresiones se publican íntegras en `reports/security/secrets_scan.json` y se
revisan una por una. **No se ignoran hallazgos para obtener un reporte verde.**
