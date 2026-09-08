# Harness unificado de desarrollo y calidad de Matrix RH.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "setup", "install", "bootstrap", "check", "ci", "test", "backend-test", "frontend-test", "lint", "typecheck", "build", "security", "validate", "package", "docker-config")]
    [string]$Command = "help"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Invoke-Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Name fallo con codigo $LASTEXITCODE." }
}

function Require-Command([string]$Name, [string]$Help) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) { throw "No se encontro '$Name'. $Help" }
}

function Invoke-Uv([string[]]$Arguments) {
    if (Get-Command uv -ErrorAction SilentlyContinue) { & uv @Arguments; return }
    if (Get-Command python -ErrorAction SilentlyContinue) { & python -m uv @Arguments; return }
    throw "No se encontro uv. Instalelo con un canal aprobado."
}

function Invoke-Backend([string[]]$Arguments) {
    if (-not (Test-Path -LiteralPath $VenvPython)) { throw "No existe .venv. Ejecute '.\MATRIX-DEV.ps1 setup'." }
    $PreviousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $BackendRoot
        Push-Location $BackendRoot
        try { & $VenvPython @Arguments } finally { Pop-Location }
    }
    finally { $env:PYTHONPATH = $PreviousPythonPath }
}

function Invoke-Frontend([string[]]$Arguments) {
    Require-Command "npm" "Instale Node.js 22 LTS."
    Push-Location $FrontendRoot
    try { & npm.cmd @Arguments } finally { Pop-Location }
}

function Setup-Project {
    Invoke-Step "Backend: sincronizar uv.lock" {
        $PreviousUvEnvironment = $env:UV_PROJECT_ENVIRONMENT
        try {
            $env:UV_PROJECT_ENVIRONMENT = Join-Path $ProjectRoot ".venv"
            Push-Location $BackendRoot
            try { Invoke-Uv @("sync", "--extra", "dev", "--locked") } finally { Pop-Location }
        }
        finally { $env:UV_PROJECT_ENVIRONMENT = $PreviousUvEnvironment }
    }
    Invoke-Step "Frontend: instalar package-lock.json sin scripts" { Push-Location $FrontendRoot; try { & npm.cmd ci --ignore-scripts } finally { Pop-Location } }
}

function Test-Backend { Invoke-Step "Backend: pytest offline" { Invoke-Backend @("-m", "pytest", "tests/unit", "tests/security", "-q") } }
function Test-Frontend { Invoke-Step "Frontend: Vitest" { Invoke-Frontend @("test") } }
function Invoke-Lint { Invoke-Step "Backend: Ruff" { Invoke-Backend @("-m", "ruff", "check", "app", "scripts", "tests") } }
function Invoke-Typecheck {
    Invoke-Step "Backend: mypy" { Invoke-Backend @("-m", "mypy", "app", "scripts", "seeds") }
    Invoke-Step "Frontend: TypeScript" { Invoke-Frontend @("run", "typecheck") }
}
function Build-Project { Invoke-Step "Frontend: build de produccion" { Invoke-Frontend @("run", "build") } }
function Test-Security {
    Invoke-Step "Backend: escaneo de secretos" { Invoke-Backend @("-m", "scripts.secrets_scan") }
    Invoke-Step "Cadena de suministro" { Invoke-Backend @("-m", "scripts.verify_supply_chain") }
    Invoke-Step "Frontend: dependencias productivas" { Invoke-Frontend @("audit", "--omit=dev", "--audit-level=low") }
}
function Invoke-Check {
    Invoke-Lint
    Invoke-Typecheck
    # El contrato del paquete verifica que dist exista; un clon limpio debe
    # compilarlo antes de ejecutar las pruebas backend de release.
    Build-Project
    Test-Backend
    Test-Frontend
    Test-Security
}

switch ($Command) {
    { $_ -in "setup", "install", "bootstrap" } { Setup-Project; break }
    { $_ -in "check", "ci" } { Invoke-Check; break }
    "test"          { Test-Backend; Test-Frontend }
    "backend-test"  { Test-Backend }
    "frontend-test" { Test-Frontend }
    "lint"          { Invoke-Lint }
    "typecheck"     { Invoke-Typecheck }
    "build"         { Build-Project }
    "security"      { Test-Security }
    "validate"      { & (Join-Path $ProjectRoot "windows\Validate-MatrixRH.ps1") }
    "package"       { Invoke-Step "Paquete ZIP unificado" { Invoke-Backend @("-m", "scripts.package_release") } }
    "docker-config" { Require-Command "docker" "Instale Docker Desktop."; Invoke-Step "Docker Compose" { Push-Location $ProjectRoot; try { & docker compose config --quiet } finally { Pop-Location } } }
    default {
        Write-Host @"
Matrix RH - harness de desarrollo

  setup | install | bootstrap  Instala las dependencias reproduciblemente
  check | ci                   Gate offline completo
  test                         Pruebas offline backend + frontend
  backend-test / frontend-test Pruebas por tecnologia
  lint / typecheck / build     Gates especializados
  security                     Secretos, supply chain y npm audit
  validate                     Validacion integral con servicios locales
  package                      Genera el ZIP de instalacion unificado
  docker-config                Valida Docker Compose
"@
    }
}
