<!-- Creado por Aldo Garcia. -->

# Inicio rápido para el operador

## Primera instalación en Windows

1. Extraiga el ZIP en una ruta local estable; por ejemplo,
   `C:\wamp64\www\matrix-rh`.
2. Inicie MySQL/MariaDB de WAMP y Ollama.
3. Confirme `py -3.12 --version` y `ollama list`.
4. Ejecute `INSTALAR_MATRIX_RH.bat` con doble clic.
5. Espere `INSTALACION COMPLETADA`; si falla, no cree tablas, PID ni archivos
   `.env` manualmente: ejecute `DIAGNOSTICO_MATRIX_RH.bat`.
6. Ejecute `INICIAR_MATRIX_RH.bat` y abra
   `http://127.0.0.1:8000` si el navegador no se abre solo.

El instalador reutiliza una instalación propia, pero no adopta ni modifica una
base preexistente sin autorización explícita. Si el nombre configurado ya está
ocupado, elige un nombre libre y conserva la base ajena.

## Operación normal

| Acción | Archivo |
|---|---|
| Instalar e inicializar (instala y arranca) | `INSTALAR_MATRIX_RH.bat` |
| Iniciar backend e interfaz (usos posteriores) | `INICIAR_MATRIX_RH.bat` |
| Detener sólo los procesos del proyecto | `DETENER_MATRIX_RH.bat` |
| Diagnóstico de sólo lectura | `DIAGNOSTICO_MATRIX_RH.bat` |
| Validación integral | `powershell -ExecutionPolicy Bypass -File windows\Validate-MatrixRH.ps1` |
| Autoarranque opcional | `INSTALAR_MATRIX_RH.bat -WithAutostart` |

`/health` significa que el proceso vive; `/ready` significa que sus dependencias
obligatorias están listas. Una respuesta positiva de `/health` no reemplaza
`/ready`.

## Diagnóstico mínimo

1. Ejecute `DIAGNOSTICO_MATRIX_RH.bat`.
2. Corrija el **primer** `FAIL`; los fallos siguientes pueden ser consecuencia.
3. Revise `var\logs\backend-*.err.log` si el proceso termina al arrancar.
4. Confirme los modelos exactos con `ollama list` y su carga con `ollama ps`.
5. Confirme que el archivo documental tiene estado `indexed` antes de probar su
   resumen.

No publique `.env`, contraseñas administrativas, tokens, logs completos ni
documentos empresariales al solicitar soporte. Comparta el código de error, el
check que falla y el mensaje seguro del diagnóstico.

## Credenciales de desarrollo

Las cuentas `Matrix` y `MatrixR1` son fixtures sintéticos para
`APP_ENV=development|test`; no son cuentas corporativas. Deben deshabilitarse
antes de producción y nunca deben coexistir con el proveedor local activo en
`APP_ENV=production`.

Para operación detallada consulte [`RUNBOOK.md`](RUNBOOK.md) y, ante un fallo,
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
