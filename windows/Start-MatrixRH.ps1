# Creado por Aldo Garcia.
<#
.SYNOPSIS
    Arranca Matrix RH (backend + frontend servido same-origin) y abre el navegador.

.DESCRIPTION
    Seccion 39.3: preflight, verificacion de dependencias, arranque del backend,
    espera a /health y /ready, apertura del navegador, ruta de logs visible y
    proteccion frente a arranques duplicados.
#>

[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$SkipPreflight,
    [int]$ReadyTimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common-MatrixRH.ps1")

$root = Get-MatrixRoot
$url = Get-MatrixBackendUrl

Write-Section "MATRIX RH - ARRANQUE"

# --- ya esta arriba? ---------------------------------------------------------
if (Test-MatrixBackendUp) {
    Write-Ok "Matrix RH ya esta en ejecucion en $url (no se duplica el proceso)."
    if (-not $NoBrowser) { Start-Process $url }
    exit 0
}

if (-not (Test-MatrixVenv)) {
    Write-Fail "No existe el entorno virtual."
    Write-Host "         Ejecute primero INSTALAR_MATRIX_RH.bat"
    exit 1
}

New-MatrixRuntimeDirs

# --- preflight ---------------------------------------------------------------
if (-not $SkipPreflight) {
    Write-Section "Preflight"
    $code = Invoke-MatrixPython -Arguments @("-m", "scripts.preflight")
    if ($code -ne 0) {
        Write-Fail "El preflight fallo: Matrix RH no se arranca."
        Write-Host "         Ejecute DIAGNOSTICO_MATRIX_RH.bat para ver el detalle."
        exit 1
    }
}

# --- arranque ----------------------------------------------------------------
Write-Section "Arrancando el backend"
$logDir = Get-MatrixLogDir
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outLog = Join-Path $logDir "backend-$stamp.log"
$errLog = Join-Path $logDir "backend-$stamp.err.log"

$python = Get-MatrixPython
$env:PYTHONPATH = Get-MatrixBackendDir
$process = Start-Process -FilePath $python `
    -ArgumentList @("-m", "scripts.bootstrap", "serve", "--skip-preflight") `
    -WorkingDirectory (Get-MatrixBackendDir) `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path (Get-MatrixPidFile) -Value $process.Id -Encoding ASCII
Write-Step "Proceso backend PID $($process.Id)"
Write-Step "Log de salida: $outLog"
Write-Step "Log de errores: $errLog"

# --- espera a /health --------------------------------------------------------
Write-Step "Esperando a que el backend responda..."
$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        Write-Fail "El backend termino inesperadamente (codigo $($process.ExitCode))."
        Write-Host "         Ultimas lineas del log de errores:"
        if (Test-Path $errLog) { Get-Content $errLog -Tail 20 | ForEach-Object { Write-Host "           $_" } }
        exit 1
    }
    if (Test-MatrixBackendUp -TimeoutSec 2) { $healthy = $true; break }
    Start-Sleep -Seconds 2
}

if (-not $healthy) {
    Write-Fail "El backend no respondio a /health en $ReadyTimeoutSeconds segundos."
    if (Test-Path $errLog) { Get-Content $errLog -Tail 20 | ForEach-Object { Write-Host "           $_" } }
    exit 1
}
Write-Ok "Backend vivo en $url"

# --- espera a /ready ---------------------------------------------------------
Write-Step "Verificando dependencias obligatorias (/ready)..."
$ready = $false
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    if (Test-MatrixBackendReady -TimeoutSec 5) { $ready = $true; break }
    Start-Sleep -Seconds 3
}

if ($ready) {
    Write-Ok "Todas las dependencias obligatorias estan operativas."
}
else {
    Write-Warn "El backend esta vivo pero NO listo (/ready = false)."
    try {
        $detail = Invoke-RestMethod -Uri "$url/ready" -TimeoutSec 5
        foreach ($component in $detail.components) {
            if (-not $component.ok) { Write-Warn "  $($component.name): $($component.detail)" }
        }
    }
    catch { Write-Warn "  No fue posible leer el detalle de /ready." }
    Write-Host "         Ejecute DIAGNOSTICO_MATRIX_RH.bat para el diagnostico completo."
}

# --- frontend ----------------------------------------------------------------
$dist = Join-Path $root "frontend\dist\index.html"
if (-not (Test-Path $dist)) {
    Write-Warn "No hay build del frontend: solo estara disponible la API en $url/api/v1"
    Write-Host "         Repita INSTALAR_MATRIX_RH.bat para compilar desde package-lock.json."
}
else {
    Write-Ok "Interfaz servida same-origin desde $url"
}

if (-not $NoBrowser) {
    Start-Process $url
}

Write-Section "MATRIX RH EN EJECUCION"
Write-Host "  URL:      $url"
Write-Host "  Logs:     $logDir"
Write-Host "  Detener:  DETENER_MATRIX_RH.bat"
Write-Host ""
exit 0
