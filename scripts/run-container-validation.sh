#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

MODE="${1:-targeted}"
VENV_DIR="${VENV_DIR:-.venv}"
BOOTSTRAP_PYTHON="${BOOTSTRAP_PYTHON:-python3}"
FORCE_REINSTALL="${FORCE_REINSTALL:-0}"
FINGERPRINT_FILE="${VENV_DIR}/.deps-fingerprint"

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

CURRENT_FINGERPRINT="$("${BOOTSTRAP_PYTHON}" - <<'PY'
import hashlib
from pathlib import Path

print(hashlib.sha256(Path("pyproject.toml").read_bytes()).hexdigest())
PY
)"

if [[ "${FORCE_REINSTALL}" == "1" ]] || [[ ! -f "${FINGERPRINT_FILE}" ]] || [[ "$(cat "${FINGERPRINT_FILE}")" != "${CURRENT_FINGERPRINT}" ]]; then
  echo "Installing/updating project dependencies in ${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/pip" install -e ".[dev]"
  printf "%s" "${CURRENT_FINGERPRINT}" > "${FINGERPRINT_FILE}"
else
  echo "Dependency fingerprint unchanged; skipping pip install"
fi

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
