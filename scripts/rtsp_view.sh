#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="$PROJECT_ROOT/config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
  exit 1
fi

if ! command -v mpv >/dev/null 2>&1; then
  echo "mpv not found in PATH"
  exit 1
fi

# Общие параметры RTSP из конфига (порт / path по умолчанию)
rtsp_port=$(grep -E '^[[:space:]]*rtsp_port:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*([0-9]+).*/\1/' | sed 's/[[:space:]]*$//')
rtsp_port=${rtsp_port:-8554}

# Зададаны дефолты для live/preview
live_path="live"
preview_path="preview"

echo "Выбериnt поток для просмотра:"
echo "  1) live     (rtsp://127.0.0.1:${rtsp_port}/${live_path})"
echo "  2) preview  (rtsp://127.0.0.1:${rtsp_port}/${preview_path})"
echo "  0) выход"
read -rp "Ваш выбор [0-2]: " choice

case "$choice" in
  1)
    RTSP_URL="rtsp://127.0.0.1:${rtsp_port}/${live_path}"
    ;;
  2)
    RTSP_URL="rtsp://127.0.0.1:${rtsp_port}/${preview_path}"
    ;;
  0)
    echo "Выход."
    exit 0
    ;;
  *)
    echo "Неизвестный выбор: $choice"
    exit 1
    ;;
esac

echo "Открываю поток: $RTSP_URL"

mpv \
  --hwdec=auto \
  --rtsp-transport=tcp \
  --title="$RTSP_URL" \
  "$RTSP_URL"