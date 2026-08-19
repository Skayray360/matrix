<!-- Creado por Aldo Garcia. -->

# windows/

Scripts PowerShell que usan los `.bat` de la raíz. **La lógica de negocio no vive
aquí**: estos scripts delegan en los módulos Python del backend.

| Script | Papel | Lanzador `.bat` |
|---|---|---|
| `Common-MatrixRH.ps1` | Funciones compartidas: rutas, Python, Ollama, salud, WAMP | — |
| `Install-MatrixRH.ps1` | Instalación idempotente en 10 pasos | `INSTALAR_MATRIX_RH.bat` (instala **e inicializa**: al terminar encadena `Start-MatrixRH.ps1`) |
| `Start-MatrixRH.ps1` | Preflight, arranque, espera a `/health` y `/ready`, navegador | `INICIAR_MATRIX_RH.bat` |
| `Stop-MatrixRH.ps1` | Detención ordenada; sólo procesos de este proyecto | `DETENER_MATRIX_RH.bat` |
| `Diagnose-MatrixRH.ps1` | Diagnóstico de **solo lectura** | `DIAGNOSTICO_MATRIX_RH.bat` |
| `Validate-MatrixRH.ps1` | Validación completa con evidencia | — (ejecutar por PowerShell) |
| `Install-Autostart.ps1` | Autoarranque opcional por tarea programada | — (`INSTALAR_MATRIX_RH.bat -WithAutostart`) |

## Por qué esta separación

El diagnóstico que ve el operador en Windows es exactamente el que ejecutan las
pruebas: ambos llaman a `scripts.preflight`.
