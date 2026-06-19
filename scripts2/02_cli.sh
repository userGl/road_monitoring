#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_ACTIVATE="${APP_DIR}/.venv/bin/activate"
MAIN_PY="${APP_DIR}/scripts2/cli/main.py"
MAIN_MODULE="scripts2.cli.main"

if [[ ! -f "${MAIN_PY}" ]]; then
  echo "Не найден main.py: ${MAIN_PY}"
  exit 1
fi

if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "Не найден .venv: ${VENV_ACTIVATE}"
  echo "Активируй/создай venv и установи зависимости."
  exit 1
fi

# shellcheck source=/dev/null
source "${VENV_ACTIVATE}"

cd "${APP_DIR}"
exec python -m "${MAIN_MODULE}" "$@"
