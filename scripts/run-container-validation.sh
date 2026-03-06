#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:-targeted}"
VENV_DIR="${VENV_DIR:-.venv}"
BOOTSTRAP_PYTHON="${BOOTSTRAP_PYTHON:-python3}"

if [[ "${MODE}" != "targeted" && "${MODE}" != "full" ]]; then
  echo "Usage: $0 [targeted|full]"
  exit 2
fi

if ! command -v "${BOOTSTRAP_PYTHON}" >/dev/null 2>&1; then
  echo "ERROR: ${BOOTSTRAP_PYTHON} not found in PATH."
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  "${BOOTSTRAP_PYTHON}" -m venv "${VENV_DIR}"
fi

echo "Installing/updating project dependencies in ${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install -e ".[dev]"

echo "Checking test dependency imports"
"${VENV_DIR}/bin/python" scripts/test.py check

if [[ "${MODE}" == "full" ]]; then
  echo "Running full test suite"
  "${VENV_DIR}/bin/python" scripts/test.py full
  exit $?
fi

echo "Running targeted PR validation suite"
"${VENV_DIR}/bin/pytest" \
  -o addopts="" \
  tests/auth_server/unit/test_server.py \
  tests/unit/api/test_server_routes.py \
  tests/unit/services/federation/test_anthropic_client.py \
  tests/unit/services/test_federation_reconciliation.py \
  tests/unit/search/test_faiss_service.py \
  tests/unit/health/test_health_service.py
