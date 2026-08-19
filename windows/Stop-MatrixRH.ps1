# Creado por Aldo Garcia.
<#
.SYNOPSIS
    Detiene el backend de Matrix RH de forma ordenada.

.DESCRIPTION
    Usa el PID registrado por Start-MatrixRH.ps1. Si ese archivo falta o el
    proceso ya no existe, busca por linea de comandos, pero NUNCA mata procesos
    de Python ajenos al proyecto.
#>

[CmdletBinding()]
param([switch]$Force)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "Common-MatrixRH.ps1")

Write-Section "MATRIX RH - DETENER"

$pidFile = Get-MatrixPidFile
$stopped = $false

if (Test-Path $pidFile) {
    $recorded = (Get-Content $pidFile -Raw).Trim()
    if ($recorded -match '^\d+$') {
        $process = Get-Process -Id ([int]$recorded) -ErrorAction SilentlyContinue
        if ($process) {
            Write-Step "Deteniendo PID $recorded..."
            Stop-Process -Id ([int]$recorded) -Force:$Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

if (-not $stopped) {
    # Se filtra por la ruta del proyecto: no se toca ningun otro Python.
    $backendDir = Get-MatrixBackendDir
    $candidates = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*scripts.bootstrap*serve*" -and $_.CommandLine -like "*$([regex]::Escape((Get-MatrixRoot)))*" }
    foreach ($candidate in $candidates) {
        Write-Step "Deteniendo PID $($candidate.ProcessId) ($backendDir)..."
        Stop-Process -Id $candidate.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
}

Start-Sleep -Seconds 2
if (Test-MatrixBackendUp -TimeoutSec 2) {
    Write-Warn "El backend sigue respondiendo. Reintente con -Force."
    exit 1
}

if ($stopped) { Write-Ok "Matrix RH detenido." }
else { Write-Ok "Matrix RH no estaba en ejecucion." }
exit 0
