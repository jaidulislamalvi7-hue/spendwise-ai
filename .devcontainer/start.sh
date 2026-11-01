#!/usr/bin/env bash
# SpendWise AI - start FastAPI and Streamlit for Codespaces development.
#
# Runs as postStartCommand (and can be run manually). Uses the project virtual
# environment created by setup.sh. Safe to re-run: a service already listening
# on its port is left alone.
#
# Migrations are NOT run here. Apply them explicitly; see the README.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/.." && pwd)"
VENV="${REPO_ROOT}/.venv"
LOG_DIR="${HERE}/logs"
mkdir -p "${LOG_DIR}"

if [ ! -x "${VENV}/bin/python" ]; then
    echo "ERROR: ${VENV}/bin/python not found." >&2
    echo "Run 'bash .devcontainer/setup.sh' first." >&2
    exit 1
fi

is_listening() {
    (echo >"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

wait_for_port() {
    local port="$1" tries="${2:-30}" i=0
    while [ "${i}" -lt "${tries}" ]; do
        if is_listening "${port}"; then
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    return 1
}

start_service() {
    local name="$1" port="$2" dir="$3" log="${LOG_DIR}/$1.log"
    shift 3
    if is_listening "${port}"; then
        echo "==> ${name}: already listening on ${port}"
        return 0
    fi
    echo "==> ${name}: starting on ${port} (log: ${log})"
    ( cd "${dir}" && nohup "$@" >"${log}" 2>&1 & )
    if wait_for_port "${port}" "${START_TIMEOUT:-60}"; then
        echo "==> ${name}: ready on ${port}"
    else
        echo "ERROR: ${name} did not listen on ${port} within ${START_TIMEOUT:-60}s." >&2
        echo "----- last 40 lines of ${log} -----" >&2
        tail -n 40 "${log}" >&2 || true
        return 1
    fi
}

echo "==> Starting SpendWise AI"
start_service "backend" 8000 "${REPO_ROOT}/backend" \
    "${VENV}/bin/python" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

start_service "streamlit" 8501 "${REPO_ROOT}/frontend" \
    "${VENV}/bin/python" -m streamlit run streamlit_app.py \
    --server.port 8501 --server.address 0.0.0.0

echo ""
echo "Streamlit: http://localhost:8501    API: http://localhost:8000/docs"
