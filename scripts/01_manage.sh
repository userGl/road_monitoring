#!/usr/bin/env bash

set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8081/api/v1}"
CONFIG_URL="${BASE_URL}/config"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_RTSP_SCRIPT="${SCRIPT_DIR}/start_mediamtx_rtsp.sh"
VIEW_RTSP_SCRIPT="${SCRIPT_DIR}/rtsp_view.sh"

require_bin() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Ошибка: не найдено '$1'"
    exit 1
  fi
}

json_get() {
  local json="$1"
  local expr="$2"

  python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
value = data
for key in '${expr}'.split('.'):
    value = value[key]
print(value)
" <<< "${json}"
}

print_config() {
  local json="$1"

  local stream_enabled
  local conf
  local model_path

  stream_enabled="$(json_get "${json}" "stream.enable_output_stream")"
  conf="$(json_get "${json}" "detector.confidence_threshold")"
  model_path="$(json_get "${json}" "detector.model_path")"

  echo
  echo "================ CURRENT CONFIG ================"
  echo "stream.enable_output_stream  : ${stream_enabled}"
  echo "detector.confidence_threshold: ${conf}"
  echo "detector.model_path          : ${model_path}"
  echo "==============================================="
  echo
}

pretty_print_json() {
  local json="$1"
  python3 -m json.tool <<< "${json}"
}

get_config_raw() {
  curl -sS --fail "${CONFIG_URL}"
}

patch_config() {
  local payload="$1"

  echo
  echo "Отправка PATCH..."

  local response
  if ! response="$(curl -sS --fail -X PATCH "${CONFIG_URL}" \
    -H "Content-Type: application/json" \
    -d "${payload}")"; then
    echo "Ошибка PATCH-запроса"
    return 1
  fi

  echo "Ответ API:"
  pretty_print_json "${response}"
  echo
  return 0
}

change_confidence() {
  local value

  read -r -p "Введите новое значение confidence_threshold [0..1]: " value

  if [[ ! "${value}" =~ ^(0(\.[0-9]+)?|1(\.0+)?)$ ]]; then
    echo "Ошибка: значение должно быть числом от 0 до 1"
    return 1
  fi

  patch_config "{
    \"detector\": {
      \"confidence_threshold\": ${value}
    }
  }"
}

change_stream() {
  local choice

  echo
  echo "1) true"
  echo "2) false"
  read -r -p "Выберите новое значение enable_output_stream: " choice

  case "${choice}" in
    1)
      patch_config '{
        "stream": {
          "enable_output_stream": true
        }
      }'
      ;;
    2)
      patch_config '{
        "stream": {
          "enable_output_stream": false
        }
      }'
      ;;
    *)
      echo "Некорректный выбор"
      return 1
      ;;
  esac
}

change_model_path() {
  local model_path
  local payload

  read -r -p "Введите новый model_path: " model_path

  if [[ -z "${model_path}" ]]; then
    echo "Ошибка: model_path не должен быть пустым"
    return 1
  fi

  payload="$(python3 -c '
import json, sys
model_path = sys.argv[1]
print(json.dumps({"detector": {"model_path": model_path}}, ensure_ascii=False))
' "${model_path}")"

  patch_config "${payload}"
}

open_in_new_terminal() {
  local title="$1"
  local script_path="$2"

  if command -v gnome-terminal >/dev/null 2>&1; then
    gnome-terminal --title="${title}" -- bash -lc "\"${script_path}\"; echo; read -n 1 -s -r -p 'Нажми любую клавишу для закрытия...'"
    return 0
  fi

  if command -v x-terminal-emulator >/dev/null 2>&1; then
    x-terminal-emulator -e bash -lc "\"${script_path}\"; echo; read -n 1 -s -r -p 'Нажми любую клавишу для закрытия...'"
    return 0
  fi

  echo "Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator)"
  return 1
}

start_rtsp_publisher() {
  if [[ ! -f "${START_RTSP_SCRIPT}" ]]; then
    echo "Скрипт не найден: ${START_RTSP_SCRIPT}"
    return 1
  fi

  chmod +x "${START_RTSP_SCRIPT}" 2>/dev/null || true
  open_in_new_terminal "RTSP Publisher" "${START_RTSP_SCRIPT}"
}

start_rtsp_viewer() {
  if [[ ! -f "${VIEW_RTSP_SCRIPT}" ]]; then
    echo "Скрипт не найден: ${VIEW_RTSP_SCRIPT}"
    return 1
  fi

  chmod +x "${VIEW_RTSP_SCRIPT}" 2>/dev/null || true
  open_in_new_terminal "RTSP Viewer" "${VIEW_RTSP_SCRIPT}"
}

main_loop() {
  while true; do
    local config_json

    if ! config_json="$(get_config_raw)"; then
      echo
      echo "Не удалось получить текущую конфигурацию: ${CONFIG_URL}"
      echo "Проверь, что сервис запущен."
      echo
      read -r -p "Нажми Enter для повтора..."
      continue
    fi

    print_config "${config_json}"

    echo "Что сделать?"
    echo "1) Изменить detector.confidence_threshold"
    echo "2) Изменить stream.enable_output_stream"
    echo "3) Изменить detector.model_path"
    echo "4) Показать полный JSON"
    echo "5) Запустить start_mediamtx_rtsp.sh в новом терминале"
    echo "6) Запустить rtsp_view.sh в новом терминале"
    echo "0) Выход"
    echo

    read -r -p "Выбор: " action

    case "${action}" in
      1)
        change_confidence
        ;;
      2)
        change_stream
        ;;
      3)
        change_model_path
        ;;
      4)
        pretty_print_json "${config_json}"
        ;;
      5)
        start_rtsp_publisher
        ;;
      6)
        start_rtsp_viewer
        ;;
      0)
        echo "Выход"
        break
        ;;
      *)
        echo "Некорректный выбор"
        ;;
    esac

    echo
    read -r -p "Нажми Enter, чтобы вернуться в начало меню..."
  done
}

require_bin curl
require_bin python3

main_loop
