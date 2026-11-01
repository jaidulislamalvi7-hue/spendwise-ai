#!/usr/bin/env bash
# SpendWise AI - Codespaces dependency installation.
#
# Runs as postCreateCommand, inside the dev container, after the workspace is
# mounted. Secret generation happens earlier, in init-env.sh (initializeCommand).
#
# Creates a project-local virtual environment and installs into it -- no
# pip --user, no --break-system-packages.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/.." && pwd)"
VENV="${REPO_ROOT}/.venv"

echo "==> Creating virtual environment at ${VENV}"
python3 -m venv "${VENV}"

echo "==> Installing dependencies"
"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/python" -m pip install -r "${REPO_ROOT}/requirements.txt"
"${VENV}/bin/python" -m pip install -r "${REPO_ROOT}/requirements-dev.txt"

# Sanity check: every module the two services import at startup must resolve.
# A partial install (missing psycopg, uvicorn, streamlit or alembic) would
# otherwise surface much later as an opaque crash inside start.sh, so the real
# traceback is printed here instead of being discarded.
IMPORTS="fastapi, uvicorn, streamlit, sqlalchemy, alembic, psycopg"
IMPORTS="${IMPORTS}, pydantic_settings, pandas, numpy, sklearn, httpx, jwt, argon2"

if ! import_errors="$("${VENV}/bin/python" -c "import ${IMPORTS}" 2>&1)"; then
    echo "ERROR: dependency installation did not produce an importable environment." >&2
    echo "${import_errors}" >&2
    exit 1
fi

echo "==> Setup complete."
echo "    Interpreter: ${VENV}/bin/python"
echo "    Next: apply migrations, then start the app (see README, Codespaces section)."
