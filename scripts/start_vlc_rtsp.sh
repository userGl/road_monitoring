#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="$PROJECT_ROOT/config.yaml"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Config not found: $CONFIG_PATH"
  exit 1
fi

video_rel=$(grep -E '^[[:space:]]*video:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*"?(.*)"?/\1/')
rtsp_port=$(grep -E '^[[:space:]]*rtsp_port:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*([0-9]+).*/\1/')
rtsp_path=$(grep -E '^[[:space:]]*rtsp_path:' "$CONFIG_PATH" | sed -E 's/^[^:]+:[[:space:]]*"?(.*)"?/\1/')

if [[ -z "$video_rel" ]]; then
  echo "video not found in config.yaml"
  exit 1
fi

if [[ -z "$rtsp_port" ]]; then
  rtsp_port=8554
fi

if [[ -z "$rtsp_path" ]]; then
  rtsp_path="live"
fi

video_path="$PROJECT_ROOT/$video_rel"

if [[ ! -f "$video_path" ]]; then
  echo "Video file not found: $video_path"
  exit 1
fi

if command -v vlc >/dev/null 2>&1; then
  VLC_BIN="vlc"
else
  echo "VLC not found in PATH"
  exit 1
fi

echo "Starting VLC RTSP server..."
echo "Video: $video_path"
echo "URL: rtsp://127.0.0.1:$rtsp_port/$rtsp_path"

"$VLC_BIN" \
  --loop \
  "$video_path" \
  ":sout=#gather:rtp{sdp=rtsp://:$rtsp_port/$rtsp_path}" \
  ":network-caching=500" \
  ":sout-all" \
  ":sout-keep"