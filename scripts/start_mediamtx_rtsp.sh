#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="$PROJECT_ROOT/config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
  exit 1
fi

video_rel=$(grep -E '^[[:space:]]*video:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*"?(.*)"?/\1/' | sed 's/[[:space:]]*$//')
rtsp_port=$(grep -E '^[[:space:]]*rtsp_port:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*([0-9]+).*/\1/' | sed 's/[[:space:]]*$//')
rtsp_path=$(grep -E '^[[:space:]]*rtsp_path:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*"?(.*)"?/\1/' | sed 's/[[:space:]]*$//')

if [[ -z "${video_rel:-}" ]]; then
  echo "video not found in config.yaml"
  exit 1
fi

rtsp_port=${rtsp_port:-8554}
rtsp_path=${rtsp_path:-live}

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

if docker ps --format '{{.Names}}' | grep -qx 'mediamtx'; then
  echo "MediaMTX is already running in Docker"
else
  echo "Starting MediaMTX in Docker..."
  docker run -d --rm --name mediamtx --network=host bluenviron/mediamtx:latest >/dev/null
fi

echo "Waiting for RTSP server on rtsp://127.0.0.1:${rtsp_port}/${rtsp_path} ..."
sleep 2

echo "Publishing file: $video_path"
echo "RTSP URL: rtsp://127.0.0.1:${rtsp_port}/${rtsp_path}"

ffmpeg -re -stream_loop -1 -i "$video_path" \
  -an \
  -c:v copy \
  -rtsp_transport tcp -f rtsp \
  "rtsp://127.0.0.1:${rtsp_port}/${rtsp_path}"