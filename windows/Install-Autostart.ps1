# Creado por Aldo Garcia.
<#
.SYNOPSIS
    Instala (o desinstala) el autoarranque de Matrix RH al iniciar sesion.

.DESCRIPTION
    Crea una tarea programada del usuario actual que ejecuta
    INICIAR_MATRIX_RH.bat sin abrir el navegador. Es OPCIONAL y esta documentada:
    Matrix RH funciona perfectamente sin autoarranque.

    No requiere privilegios de administrador: la tarea se registra en el ambito
    del usuario, no del equipo.
#>

[CmdletBinding()]
param([switch]$Remove)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "Common-MatrixRH.ps1")

$taskName = "MatrixRH-Autoarranque"
$root = Get-MatrixRoot
$starter = Join-Path $root "INICIAR_MATRIX_RH.bat"

Write-Section "MATRIX RH - AUTOARRANQUE"

if ($Remove) {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Ok "Autoarranque eliminado."
    }
    else { Write-Ok "No habia autoarranque instalado." }
    exit 0
}

if (-not (Test-Path $starter)) {
    Write-Fail "No se encontro INICIAR_MATRIX_RH.bat en $root"
    exit 1
}

try {
    $action = New-ScheduledTaskAction -Execute "cmd.exe" `
        -Argument "/c `"$starter`" -NoBrowser" -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero)

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Arranque automatico de Matrix RH" -Force | Out-Null

    Write-Ok "Autoarranque instalado como tarea programada '$taskName'."
    Write-Host "  Para quitarlo: powershell -File windows\Install-Autostart.ps1 -Remove"
}
catch {
    Write-Fail "No fue posible registrar la tarea programada."
    Write-Host "         Detalle: $($_.Exception.Message)"
    exit 1
}
exit 0
