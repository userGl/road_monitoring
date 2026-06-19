#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

VENV_ACTIVATE="${APP_DIR}/.venv/bin/activate"
MANAGER="${APP_DIR}/scripts/manage.py"

if [[ ! -f "${MANAGER}" ]]; then
  echo "Не найден manage.py: ${MANAGER}"
  exit 1
fi

if [[ ! -f "${VENV_ACTIVATE}" ]]; then
  echo "Не найден .venv: ${VENV_ACTIVATE}"
  echo "Активируй/создай venv и установи зависимости."
  exit 1
fi

# Активируем venv и запускаем Python-менеджер
# shellcheck source=/dev/null
source "${VENV_ACTIVATE}"
exec python "${MANAGER}" "$@"
