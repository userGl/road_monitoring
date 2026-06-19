#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="$SCRIPT_DIR/scripts_config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
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

video_rel="$(get_cfg_value video)"
simulator_host="$(get_cfg_value simulator_host)"
simulator_port="$(get_cfg_value simulator_port)"
simulator_path="$(get_cfg_value simulator_path)"

if [[ -z "${video_rel:-}" ]]; then
  echo "video not found in scripts_config.yaml"
  exit 1
fi

simulator_host="${simulator_host:-127.0.0.1}"
simulator_port="${simulator_port:-8554}"
simulator_path="${simulator_path:-live}"

video_path="$PROJECT_ROOT/$video_rel"
if [[ ! -f "$video_path" ]]; then
  echo "Video file not found: $video_path"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not found in PATH"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found in PATH"
  exit 1
fi

cleanup() {
  echo
  echo "Stopping streamer..."
  docker stop mediamtx >/dev/null 2>&1 || true
}
trap cleanup EXIT

if docker ps --format '{{.Names}}' | grep -qx 'mediamtx'; then
  echo "MediaMTX is already running in Docker"
else
  echo "Starting MediaMTX in Docker..."
  docker run -d --rm \
    --name mediamtx \
    --network=host \
    bluenviron/mediamtx:latest >/dev/null
fi

rtsp_url="rtsp://${simulator_host}:${simulator_port}/${simulator_path}"

echo "Waiting for RTSP server on $rtsp_url ..."
sleep 2

echo "Publishing file: $video_path"
echo "RTSP URL: $rtsp_url"

ffmpeg -re -stream_loop -1 -i "$video_path" \
  -an \
  -c:v copy \
  -rtsp_transport tcp \
  -f rtsp \
  "$rtsp_url"