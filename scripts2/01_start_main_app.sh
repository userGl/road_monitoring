#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MAIN="${APP_DIR}/main.py"
PYTHON_EXE="${APP_DIR}/.venv/bin/python"

if [[ ! -f "${MAIN}" ]]; then
  echo "Не найден main.py: ${MAIN}"
  exit 1
fi

if [[ ! -f "${PYTHON_EXE}" ]]; then
  echo "Не найден python в venv: ${PYTHON_EXE}"
  echo "Создай/настрой .venv и установи зависимости."
  exit 1
fi

cd "${APP_DIR}"
exec "${PYTHON_EXE}" "${MAIN}" "$@"