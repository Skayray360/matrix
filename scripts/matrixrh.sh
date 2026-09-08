#!/usr/bin/env bash
# Creado por Aldo Garcia.
# ---------------------------------------------------------------------------
# Equivalente shell de los .bat de la raiz para entornos no-Windows.
# No duplica logica: delega en los mismos modulos Python del backend.
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_PY="${ROOT}/.venv/bin/python"
BACKEND="${ROOT}/backend"
PID_FILE="${ROOT}/var/matrixrh-backend.pid"
LOG_DIR="${ROOT}/var/logs"

info()  { printf '  \033[0;90m-> %s\033[0m\n' "$1"; }
ok()    { printf '  \033[0;32m[ OK ]\033[0m %s\n' "$1"; }
warn()  { printf '  \033[0;33m[WARN]\033[0m %s\n' "$1"; }
fail()  { printf '  \033[0;31m[FAIL]\033[0m %s\n' "$1"; }
section() { printf '\n\033[0;36m=== %s ===\033[0m\n' "$1"; }

require_python312() {
    if ! command -v python3.12 >/dev/null 2>&1; then
        fail "Se requiere Python 3.12. Instalelo y vuelva a ejecutar."
        exit 1
    fi
    ok "Python 3.12 disponible"
}

py() {
    # Ejecuta un modulo del backend con el PYTHONPATH correcto.
    ( cd "${BACKEND}" && PYTHONPATH="${BACKEND}" "${VENV_PY}" "$@" )
}

backend_url() {
    local host port
    host="$(grep -E '^\s*APP_HOST\s*=' "${ROOT}/.env" 2>/dev/null | tail -1 | cut -d= -f2 | tr -d ' ' || true)"
    port="$(grep -E '^\s*APP_PORT\s*=' "${ROOT}/.env" 2>/dev/null | tail -1 | cut -d= -f2 | tr -d ' ' || true)"
    printf 'http://%s:%s' "${host:-127.0.0.1}" "${port:-8000}"
}

cmd_install() {
    section "MATRIX RH - INSTALACION"
    require_python312

    # uv es obligatorio, igual que en el instalador de Windows: garantiza una
    # instalacion REPRODUCIBLE desde uv.lock (no resuelve rangos ni trae una
    # version publicada hace minutos).
    if ! command -v uv >/dev/null 2>&1; then
        fail "Se requiere uv para una instalacion reproducible desde uv.lock."
        fail "Instalelo por un canal autorizado y vuelva a ejecutar."
        exit 1
    fi

    if [ ! -f "${ROOT}/.env" ]; then
        cp "${ROOT}/.env.example" "${ROOT}/.env"
        # La clave de firma se genera localmente; nunca viaja en el paquete.
        local secret
        secret="$(python3.12 -c 'import secrets; print(secrets.token_hex(32))')"
        sed -i.bak "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=${secret}|" "${ROOT}/.env"
        rm -f "${ROOT}/.env.bak"
        ok "Se creo .env con una APP_SECRET_KEY nueva"
    else
        ok ".env ya existe (no se sobrescribe)"
    fi

    mkdir -p "${LOG_DIR}" "${ROOT}/var/uploads" "${ROOT}/var/qdrant" \
        "${ROOT}/reports/tests" "${ROOT}/reports/security"

    info "Sincronizando el backend desde uv.lock (--frozen)..."
    ( cd "${BACKEND}" && UV_PROJECT_ENVIRONMENT="${ROOT}/.venv" uv sync --frozen --no-dev )
    ok "Dependencias del backend sincronizadas exactamente desde uv.lock"

    if command -v npm >/dev/null 2>&1; then
        # `npm ci --ignore-scripts`, NUNCA `npm install` sin flags:
        #   * instala EXACTAMENTE lo que fija package-lock.json;
#   * `--ignore-scripts` impide preinstall/install/postinstall (el vector
#     de los gusanos del ecosistema npm) sin depender de que
#     frontend/.npmrc, que es editable, siga intacto.
        info "Instalando dependencias del frontend (npm ci --ignore-scripts)..."
        ( cd "${ROOT}/frontend" && npm ci --ignore-scripts )

        info "Verificando la cadena de suministro antes de compilar..."
        if ! py -m scripts.verify_supply_chain; then
            fail "La verificacion de cadena de suministro FALLO: no se compila el frontend."
            exit 1
        fi
        ok "Cadena de suministro verificada"

        info "Compilando el frontend..."
        ( cd "${ROOT}/frontend" && npm run build )
        ok "Frontend compilado sin ejecutar scripts de instalacion"
    else
        warn "npm/Node no disponible: el frontend no se compila"
    fi

    py -m scripts.bootstrap setup
    py -m scripts.preflight
}

cmd_start() {
    section "MATRIX RH - ARRANQUE"
    local url; url="$(backend_url)"

    if curl -fsS "${url}/health" >/dev/null 2>&1; then
        ok "Matrix RH ya esta en ejecucion en ${url}"
        return 0
    fi

    py -m scripts.preflight || { fail "El preflight fallo: no se arranca"; exit 1; }

    mkdir -p "${LOG_DIR}"
    local stamp; stamp="$(date +%Y%m%d-%H%M%S)"
    ( cd "${BACKEND}" && PYTHONPATH="${BACKEND}" nohup "${VENV_PY}" -m scripts.bootstrap serve --skip-preflight \
        >"${LOG_DIR}/backend-${stamp}.log" 2>"${LOG_DIR}/backend-${stamp}.err.log" & echo $! > "${PID_FILE}" )
    info "PID $(cat "${PID_FILE}")  logs en ${LOG_DIR}"

    local waited=0
    while [ "${waited}" -lt 180 ]; do
        if curl -fsS "${url}/health" >/dev/null 2>&1; then
            ok "Backend vivo en ${url}"
            curl -fsS "${url}/ready" >/dev/null 2>&1 && ok "Dependencias operativas" || warn "Backend vivo pero no listo"
            return 0
        fi
        sleep 2; waited=$((waited + 2))
    done
    fail "El backend no respondio en 180 s"
    tail -n 20 "${LOG_DIR}/backend-${stamp}.err.log" || true
    exit 1
}

cmd_stop() {
    section "MATRIX RH - DETENER"
    if [ -f "${PID_FILE}" ]; then
        local pid; pid="$(cat "${PID_FILE}")"
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}"; ok "Detenido PID ${pid}"
        fi
        rm -f "${PID_FILE}"
    else
        ok "Matrix RH no estaba en ejecucion"
    fi
}

cmd_diagnose() {
    section "MATRIX RH - DIAGNOSTICO"
    py -m scripts.preflight --read-only
}

cmd_validate() {
    section "MATRIX RH - VALIDACION"
    cmd_stop
    py -m scripts.bootstrap migrate
    py -m scripts.bootstrap seed
    py -m scripts.bootstrap ingest
    py -m pytest tests/unit tests/integration tests/security -q
    py -m scripts.rag_eval --retrieval --output "${ROOT}/reports/tests/rag_eval.json"
    py -m scripts.secrets_scan --allow-env --output "${ROOT}/reports/security/secrets_scan.json"
    ok "Validacion completada"
}

usage() {
    cat <<'EOF'
Uso: ./scripts/matrixrh.sh <comando>

  install    Instalacion idempotente completa
  start      Arranca el backend (preflight + espera a /health y /ready)
  stop       Detiene el backend
  diagnose   Diagnostico de solo lectura
  validate   Migraciones, seed, ingesta, pruebas, RAG y secretos

En Windows use los .bat de la raiz.
EOF
}

case "${1:-}" in
    install)  cmd_install ;;
    start)    cmd_start ;;
    stop)     cmd_stop ;;
    diagnose) cmd_diagnose ;;
    validate) cmd_validate ;;
    *)        usage; exit 1 ;;
esac
