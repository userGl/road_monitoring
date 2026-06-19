#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${SCRIPT_DIR}/scripts_config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
  exit 1
fi

if ! command -v mpv >/dev/null 2>&1; then
  echo "mpv not found in PATH"
  exit 1
fi

get_cfg_value() {
  local key="$1"
  local value

  value="$(grep -E "^[[:space:]]*${key}:" "$CONFIG_PATH" | head -n 1 | sed -E 's/^[^:]+:[[:space:]]*//')"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  echo "$value" | sed 's/[[:space:]]*$//'
}

stream_host="$(get_cfg_value output_host)"
stream_port="$(get_cfg_value output_port)"
stream_path="$(get_cfg_value output_path)"

stream_host="${stream_host:-127.0.0.1}"
stream_port="${stream_port:-8554}"
stream_path="${stream_path:-preview}"

RTSP_URL="rtsp://${stream_host}:${stream_port}/${stream_path}"

echo "Открываю поток: $RTSP_URL"

mpv \
  --hwdec=auto \
  --rtsp-transport=tcp \
  --title="$RTSP_URL" \
  "$RTSP_URL"