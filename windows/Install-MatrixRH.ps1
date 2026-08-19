# Creado por Aldo Garcia.
<#
.SYNOPSIS
    Instalacion idempotente de Matrix RH en Windows.

.DESCRIPTION
    Pasos (seccion 39.2): detectar Python 3.12 x64, detectar Ollama y sus tres
    modelos, comprobar /api/embed y la dimension real, crear el venv, instalar
    dependencias, preparar el frontend, comprobar MySQL, aplicar migraciones,
    crear los seeds sinteticos (solo development/test), ejecutar preflight y
    lanzar la ingesta inicial.

    No sobrescribe una instalacion existente: el .env se conserva, el venv se
    reutiliza y las migraciones son idempotentes.
#>

[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$SkipIngest,
    [switch]$WithAutostart
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Common-MatrixRH.ps1")

$root = Get-MatrixRoot
$failed = $false

Write-Section "MATRIX RH - INSTALACION"
Write-Host "  Raiz del proyecto: $root"

# ---------------------------------------------------------------- 1. Python --
Write-Section "1/10  Python 3.12 x64"
$systemPython = $null
$launcher = Get-Command py -ErrorAction SilentlyContinue
if ($launcher) {
    $candidate = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $candidate) { $systemPython = $candidate.Trim() }
}
if (-not $systemPython) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $systemPython = $cmd.Source }
}
if (-not (Assert-Python312 -PythonPath $systemPython)) { exit 1 }

# ----------------------------------------------------------------- 2. Ollama --
Write-Section "2/10  Ollama y modelos requeridos"
if (-not (Test-OllamaModels)) { exit 1 }

Write-Step "Comprobando el endpoint de embeddings y su dimension real..."
try {
    $body = @{ model = "embeddinggemma:latest"; input = "matrix rh dimension probe" } | ConvertTo-Json
    $embed = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/embed" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 180
    $dimension = $embed.embeddings[0].Count
    if ($dimension -ne 768) {
        Write-Fail "La dimension real de embeddinggemma es $dimension y se esperaba 768."
        Write-Host "         Matrix RH no trunca ni rellena vectores: corrija el modelo o la configuracion."
        exit 1
    }
    Write-Ok "Embeddings operativos, dimension verificada: 768"
}
catch {
    Write-Fail "El endpoint /api/embed no respondio correctamente."
    exit 1
}

# ------------------------------------------------------------------ 3. .env --
Write-Section "3/10  Configuracion (.env)"
if (-not (Test-MatrixEnvFile)) { exit 1 }
New-MatrixRuntimeDirs

$wamp = Find-WampMySql
if ($wamp) { Write-Ok "WAMP detectado en $wamp (puede proveer MySQL/MariaDB)." }
else { Write-Warn "No se detecto WAMP; se usara el DATABASE_URL configurado en .env." }

# ------------------------------------------------------------------- 4. venv --
Write-Section "4/10  Entorno virtual"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Ok "El entorno virtual ya existe (no se recrea)."
}
else {
    Write-Step "Creando .venv..."
    & $systemPython -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { Write-Fail "No fue posible crear el entorno virtual."; exit 1 }
    Write-Ok "Entorno virtual creado."
}

# ----------------------------------------------------------- 5. dependencias --
Write-Section "5/10  Dependencias de Python"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Fail "No se encontro uv. Instale uv 0.11.33 por un canal corporativo autorizado."
    Write-Host "         Confirme 'uv --version' y repita el instalador."
    exit 1
}
$uvVersionLines = @(& $uv.Source --version 2>$null)
$uvVersionExit = $LASTEXITCODE
$uvVersion = ($uvVersionLines -join "`n").Trim()
# uv puede incluir el commit y la fecha de compilacion entre la version y el
# target, por ejemplo:
#   uv 0.11.33 (fece32fc5 2026-07-28 x86_64-pc-windows-msvc)
# Ambos formatos son oficiales. Se valida semanticamente la version exacta y el
# target x64; no se compara toda la cadena generada por una compilacion concreta.
$uvVersionPattern = '^uv 0\.11\.33 \((?:[0-9A-Fa-f]{7,64}\s+\d{4}-\d{2}-\d{2}\s+)?x86_64-pc-windows-msvc\)$'
if ($uvVersionExit -ne 0 -or $uvVersionLines.Count -ne 1 -or $uvVersion -notmatch $uvVersionPattern) {
    Write-Fail "Se requiere exactamente uv 0.11.33 para Windows x64 (encontrado: $uvVersion)."
    exit 1
}
Write-Step "Sincronizando el backend desde uv.lock (--frozen)..."
Push-Location (Join-Path $root "backend")
try {
    $env:UV_PROJECT_ENVIRONMENT = (Join-Path $root ".venv")
    & $uv.Source sync --frozen --no-dev
    if ($LASTEXITCODE -ne 0) { Write-Fail "uv no pudo sincronizar backend/uv.lock."; exit 1 }
}
finally {
    Remove-Item Env:UV_PROJECT_ENVIRONMENT -ErrorAction SilentlyContinue
    Pop-Location
}
if (-not (Assert-Python312 -PythonPath $venvPython)) { exit 1 }
Write-Ok "Dependencias sincronizadas exactamente desde uv.lock."

# ---------------------------------------------------------------------------
# 6. Colision de nombre de base de datos.
#
# El .env por defecto apunta a `matrix_rh`. Si en el servidor ya existe una base
# con ese nombre creada por OTRA aplicacion, Matrix RH no la va a tocar. Se
# detecta aqui y no en el paso 8: descubrirlo a mitad de la instalacion deja el
# proceso a medias y el mensaje se pierde entre la salida del resto de pasos.
#
# Por que DESPUES de instalar las dependencias y no antes: la comprobacion se
# hace con SQLAlchemy dentro del venv. Cuando este bloque estaba en el paso 3 el
# instalador moria con `ModuleNotFoundError: No module named 'sqlalchemy'` en un
# equipo limpio, porque el venv aun no tenia nada instalado.
#
# La resolucion es no destructiva: se elige un nombre libre y se escribe en el
# .env. Nunca se borra ni se modifica la base ajena, y siempre se avisa.
# ---------------------------------------------------------------------------
Write-Section "6/10  Base de datos destino"
$envFile = Join-Path $root ".env"
$dbLine = (Select-String -Path $envFile -Pattern '^DATABASE_URL=(.+)$' | Select-Object -Last 1)
if (-not $dbLine) {
    Write-Warn "No hay DATABASE_URL en .env; el paso 8 lo verificara."
}
else {
    $dbUrl = $dbLine.Matches[0].Groups[1].Value.Trim()
    $dbName = if ($dbUrl -match '/([A-Za-z0-9_]+)(\?|$)') { $Matches[1] } else { "" }

    if (-not $dbName) {
        Write-Warn "No se pudo leer el nombre de la base en DATABASE_URL; el paso 8 lo verificara."
    }
    else {
        Write-Step "Comprobando que la base '$dbName' este libre..."
        $estado = Test-MatrixDatabaseFree -DatabaseUrl $dbUrl -DatabaseName $dbName

        if ($estado.Detalle -like 'DESCONOCIDO:*') {
            Write-Warn "No fue posible comprobar la base ($($estado.Detalle)). Se continuara; el paso 8 lo verificara."
        }
        elseif ($estado.Detalle -eq 'PROPIA') {
            Write-Ok "La base '$dbName' es de una instalacion previa de Matrix RH: se reutiliza."
        }
        elseif ($estado.Libre) {
            Write-Ok "La base '$dbName' esta libre."
        }
        else {
            # Dos motivos distintos para no usarla, con el mismo desenlace: se
            # busca otro nombre y la base del operador queda intacta.
            if ($estado.Detalle -eq 'EXISTE_VACIA') {
                Write-Warn "La base '$dbName' YA EXISTE y no la creo Matrix RH."
                Write-Host "         Esta vacia ahora, pero pudo crearla otra aplicacion." -ForegroundColor Yellow
                Write-Host "         Matrix RH no se apropia de una base que no creo." -ForegroundColor Yellow
            }
            else {
                $ajenas = ($estado.Detalle -replace '^OCUPADA:', '')
                Write-Warn "La base '$dbName' YA EXISTE y contiene tablas de otra aplicacion:"
                Write-Host "         $ajenas" -ForegroundColor Yellow
                Write-Host "         Matrix RH no va a modificarla." -ForegroundColor Yellow
            }

            # Se busca el primer nombre libre: matrix_rh_app, _app2, _app3...
            $elegido = $null
            foreach ($sufijo in @("_app", "_app2", "_app3", "_app4", "_app5")) {
                $candidato = "$dbName$sufijo"
                $prueba = Test-MatrixDatabaseFree -DatabaseUrl $dbUrl -DatabaseName $candidato
                # Un veredicto DESCONOCIDO no significa "ocupada" ni "libre": se
                # descarta el candidato en lugar de apropiarse de el a ciegas.
                if ($prueba.Detalle -like 'DESCONOCIDO:*') { continue }
                if ($prueba.Libre) { $elegido = $candidato; break }
            }

            if (-not $elegido) {
                Write-Fail "No se encontro un nombre de base libre a partir de '$dbName'."
                Write-Host "         Edite DATABASE_URL en .env con un nombre libre y vuelva a ejecutar."
                exit 1
            }

            $nuevaUrl = $dbUrl -replace "/$([regex]::Escape($dbName))(\?|$)", "/$elegido`$1"
            if (Set-MatrixEnvValue -Key 'DATABASE_URL' -Value $nuevaUrl) {
                Write-Ok "Matrix RH usara la base '$elegido' (escrito en .env)."
                Write-Host "         Su base '$dbName' queda intacta." -ForegroundColor Cyan
            }
            else {
                Write-Fail "No fue posible actualizar DATABASE_URL en .env."
                exit 1
            }
        }
    }
}

# -------------------------------------------------------------- 7. frontend --
Write-Section "7/10  Frontend"
$dist = Join-Path $root "frontend\dist\index.html"
if ($SkipFrontend) {
    Write-Warn "Compilacion del frontend omitida por parametro."
}
elseif (Test-Path $dist) {
    Write-Ok "El build del frontend ya existe."
}
else {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        Write-Warn "Node.js no esta disponible: no se compila el frontend."
        Write-Host "         Instale Node.js LTS y repita el instalador; usara pnpm-lock.yaml sin scripts."
    }
    else {
        # pnpm se ejecuta por corepack (incluido en Node): `corepack pnpm ...`
        # descarga y usa exactamente la version fijada en "packageManager" sin
        # necesitar privilegios de administrador ni modificar el PATH.
        # Se desactiva el prompt de descarga de corepack (colgaria el instalador
        # la primera vez que descarga la version de pnpm).
        $env:COREPACK_ENABLE_DOWNLOAD_PROMPT = "0"
        Push-Location (Join-Path $root "frontend")
        try {
            # ------------------------------------------------------------------
            # `pnpm install --frozen-lockfile --ignore-scripts`, NUNCA sin flags:
            #   * `--frozen-lockfile` instala EXACTAMENTE lo que fija pnpm-lock.yaml
            #     y falla si esta desincronizado; no resuelve rangos ni trae una
            #     version publicada hace minutos.
            #   * `--ignore-scripts` impide preinstall/install/postinstall, el
            #     vector por el que se propagan los gusanos del ecosistema npm:
            #     roban credenciales del entorno y republican paquetes.
            # `frontend/.npmrc` ya declara ignore-scripts=true; la bandera se
            # repite aqui para que el control no dependa de un archivo editable.
            # ------------------------------------------------------------------
            Write-Step "Instalando dependencias del frontend (pnpm install --frozen-lockfile --ignore-scripts)..."
            & corepack pnpm install --frozen-lockfile --ignore-scripts
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "pnpm install fallo. Revise que pnpm-lock.yaml este sincronizado con package.json."
            }
            else {
                Write-Ok "Dependencias del frontend instaladas sin ejecutar scripts."

                Write-Step "Verificando la cadena de suministro..."
                Pop-Location
                $code = Invoke-MatrixPython -Arguments @("-m", "scripts.verify_supply_chain")
                Push-Location (Join-Path $root "frontend")
                if ($code -ne 0) {
                    Write-Fail "La verificacion de cadena de suministro FALLO. No se compila el frontend."
                    Write-Host "         Revise los hallazgos y no continue hasta resolverlos."
                    Pop-Location
                    exit 1
                }
                Write-Ok "Cadena de suministro verificada."

                Write-Step "Compilando el frontend..."
                & corepack pnpm run build
                if ($LASTEXITCODE -ne 0) { Write-Warn "El build del frontend fallo; el backend seguira funcionando por API." }
                else { Write-Ok "Frontend compilado." }
            }
        }
        finally { if ((Get-Location).Path -like "*frontend*") { Pop-Location } }
    }
}

# ------------------------------------------------------ 8. base de datos ----
Write-Section "8/10  Base de datos y migraciones"
$code = Invoke-MatrixPython -Arguments @("-m", "scripts.bootstrap", "migrate")
if ($code -ne 0) {
    Write-Fail "Las migraciones fallaron. Revise DATABASE_URL en .env y que MySQL este arriba."
    exit 1
}
Write-Ok "Migraciones aplicadas."

Write-Step "Creando usuarios sinteticos de prueba (solo development/test)..."
$code = Invoke-MatrixPython -Arguments @("-m", "scripts.bootstrap", "seed")
if ($code -ne 0) { Write-Warn "El seed no se aplico (puede ser correcto en produccion)." }
else { Write-Ok "Usuarios sinteticos listos." }

# ------------------------------------------------------------- 9. preflight --
Write-Section "9/10  Preflight"
$code = Invoke-MatrixPython -Arguments @("-m", "scripts.preflight")
if ($code -ne 0) { Write-Fail "El preflight reporto fallos."; $failed = $true }

# -------------------------------------------------------------- 10. ingesta --
Write-Section "10/10  Ingesta inicial del conocimiento"
if ($SkipIngest) {
    Write-Warn "Ingesta inicial omitida por parametro."
}
else {
    $code = Invoke-MatrixPython -Arguments @("-m", "scripts.bootstrap", "ingest")
    if ($code -ne 0) { Write-Warn "La ingesta inicial reporto errores; revise el detalle anterior." }
    else { Write-Ok "Conocimiento indexado." }
}

if ($WithAutostart) {
    Write-Section "Autoarranque"
    & (Join-Path $PSScriptRoot "Install-Autostart.ps1")
}

Write-Section "RESULTADO DE LA INSTALACION"
if ($failed) {
    Write-Fail "La instalacion termino con fallos. Corrija lo indicado y vuelva a ejecutar."
    exit 1
}
Write-Ok "Matrix RH quedo instalado."
Write-Host ""
Write-Host "  Siguiente paso: doble clic en INICIAR_MATRIX_RH.bat" -ForegroundColor Cyan
Write-Host "  Usuarios de prueba: Matrix / Matrix RH  y  MatrixR1 / Matrix RH" -ForegroundColor Cyan
Write-Host "  (credenciales sinteticas: eliminelas antes de produccion)" -ForegroundColor DarkYellow
Write-Host ""
exit 0
