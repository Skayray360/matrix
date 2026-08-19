# Creado por Aldo Garcia.
<#
.SYNOPSIS
    Diagnostico de solo lectura de Matrix RH.

.DESCRIPTION
    Seccion 39.4. NO modifica nada: no crea directorios, no aplica migraciones,
    no arranca procesos. Delega en `scripts.preflight --read-only` y anade la
    parte que solo tiene sentido en Windows (procesos, puertos, logs recientes).
#>

[CmdletBinding()]
param([switch]$Json)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "Common-MatrixRH.ps1")

$root = Get-MatrixRoot
$url = Get-MatrixBackendUrl

# ---------------------------------------------------------------------------
# Sin entorno virtual no hay diagnostico posible.
#
# `scripts.preflight` importa pydantic, sqlalchemy y el resto del backend. Si el
# operador ejecuta el diagnostico ANTES de instalar, la version anterior moria
# con `ModuleNotFoundError: No module named 'pydantic'`: un traceback que no
# dice lo unico que hace falta saber, que Matrix RH no esta instalado todavia.
#
# Se corta aqui, se dice que falta, y se comprueban solo las dos cosas que no
# dependen del venv: que MySQL y Ollama esten escuchando. Asi el operador ya
# sabe si tendra problemas ANTES de lanzar el instalador.
# ---------------------------------------------------------------------------
if (-not (Test-MatrixVenv)) {
    if ($Json) {
        [ordered]@{
            ok      = $false
            error   = "venv_ausente"
            detalle = "Matrix RH no esta instalado en este equipo (falta .venv)."
            accion  = "Ejecute INSTALAR_MATRIX_RH.bat"
        } | ConvertTo-Json -Compress
        exit 1
    }

    Write-Section "MATRIX RH - DIAGNOSTICO INCOMPLETO"
    Write-Host "  Raiz:   $root"
    Write-Fail "Matrix RH no esta instalado en este equipo: falta el entorno virtual (.venv)."
    Write-Host "         Ejecute INSTALAR_MATRIX_RH.bat y repita el diagnostico despues."
    Write-Host "         Las comprobaciones que necesitan el backend se omiten." -ForegroundColor DarkYellow

    Write-Section "Requisitos externos (lo unico comprobable sin instalar)"
    foreach ($item in @(@{n = "MySQL"; p = 3306 }, @{n = "Ollama"; p = 11434 })) {
        $ok = (Test-NetConnection -ComputerName 127.0.0.1 -Port $item.p -WarningAction SilentlyContinue).TcpTestSucceeded
        if ($ok) { Write-Ok "$($item.n) escuchando en $($item.p)" }
        else { Write-Warn "$($item.n) sin escucha en $($item.p) (el instalador lo necesitara)" }
    }

    Write-Section "FIN DEL DIAGNOSTICO"
    exit 1
}

if ($Json) {
    exit (Invoke-MatrixPython -Arguments @("-m", "scripts.preflight", "--read-only", "--json"))
}

Write-Section "MATRIX RH - DIAGNOSTICO"
Write-Host "  Raiz:   $root"
Write-Host "  Backend: $url"

# --- entorno virtual ---------------------------------------------------------
Write-Section "Entorno de ejecucion"
Write-Ok "Entorno virtual presente."

$wamp = Find-WampMySql
if ($wamp) { Write-Ok "WAMP detectado: $wamp" } else { Write-Warn "WAMP no detectado." }

# --- preflight ---------------------------------------------------------------
Write-Section "Comprobaciones del sistema"
$code = Invoke-MatrixPython -Arguments @("-m", "scripts.preflight", "--read-only")

# --- estado del servicio -----------------------------------------------------
Write-Section "Estado del servicio"
if (Test-MatrixBackendUp) {
    Write-Ok "Backend vivo (/health)."
    if (Test-MatrixBackendReady) {
        Write-Ok "Backend listo (/ready)."
    }
    else {
        Write-Warn "Backend vivo pero no listo. Componentes con problema:"
        try {
            $detail = Invoke-RestMethod -Uri "$url/ready" -TimeoutSec 5
            foreach ($component in $detail.components) {
                if (-not $component.ok) { Write-Warn "  $($component.name): $($component.detail)" }
            }
        }
        catch { Write-Warn "  No fue posible leer /ready." }
    }
}
else {
    Write-Warn "El backend no responde (puede estar detenido a proposito)."
}

# --- procesos ----------------------------------------------------------------
Write-Section "Procesos de Matrix RH"
$procesos = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine -like "*$([regex]::Escape($root))*" }
if ($procesos) {
    foreach ($proceso in $procesos) {
        Write-Host "  PID $($proceso.ProcessId)  inicio $($proceso.CreationDate)"
    }
}
else { Write-Host "  (ninguno)" }

# --- puertos -----------------------------------------------------------------
Write-Section "Puertos"
foreach ($item in @(@{n = "Backend"; p = ([int]($url -split ':')[-1]) }, @{n = "MySQL"; p = 3306 }, @{n = "Ollama"; p = 11434 }, @{n = "Qdrant server"; p = 6333 })) {
    $ok = (Test-NetConnection -ComputerName 127.0.0.1 -Port $item.p -WarningAction SilentlyContinue).TcpTestSucceeded
    if ($ok) { Write-Ok "$($item.n) escuchando en $($item.p)" } else { Write-Warn "$($item.n) sin escucha en $($item.p)" }
}

# --- scheduler ---------------------------------------------------------------
Write-Section "Scheduler de reconciliacion (24 h)"
Invoke-MatrixPython -Arguments @("-m", "scripts.bootstrap", "status") | Out-Null

# --- logs --------------------------------------------------------------------
Write-Section "Logs recientes"
$logDir = Get-MatrixLogDir
if (Test-Path $logDir) {
    $recientes = Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3
    foreach ($log in $recientes) {
        Write-Host "  $($log.Name)  ($([int]($log.Length / 1KB)) KB, $($log.LastWriteTime))"
    }
    if (-not $recientes) { Write-Host "  (sin logs)" }
}
else { Write-Host "  (directorio de logs no creado aun)" }

Write-Section "FIN DEL DIAGNOSTICO"
exit $code
