# main.py
import threading
from pathlib import Path

import uvicorn
import yaml

from api.rest_api import app
from sensors.ffmpeg_camera import FFmpegRTSPCamera
from sensors.rtsp_streamer import create_rtsp_streamer

from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage


def load_config():
    config_path = Path(__file__).resolve().parent / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_nested(d: dict, *keys, default=None):
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


def main():
    cfg = load_config()

    input_rtsp_url = get_nested(cfg, "stream", "input_rtsp_url", default="rtsp://127.0.0.1:8554/live")
    output_rtsp_url = get_nested(cfg, "stream", "output_rtsp_url", default="rtsp://127.0.0.1:8554/preview")
    enable_output_stream = get_nested(cfg, "stream", "enable_output_stream", default=True)

    use_hwaccel = get_nested(cfg, "camera", "use_hwaccel", default=False)

    preview_width = int(get_nested(cfg, "preview", "width", default=640))
    preview_height = int(get_nested(cfg, "preview", "height", default=640))

    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    camera = FFmpegRTSPCamera(input_rtsp_url, use_hwaccel=use_hwaccel)
    print("[main] RTSP input started, API on :8081")

    meta_printed = False
    streamer = None
    pipeline = None

    try:
        for packet in camera.frames():
            if not meta_printed and camera.meta is not None:
                print(f"[main] Video meta: {camera.meta}")
                meta_printed = True

            if pipeline is None:
                pipeline = VideoPipeline(
                    stages=[
                        ResizeStage(width=preview_width, height=preview_height),
                    ]
                )

            if enable_output_stream and streamer is None:
                fps = int(camera.meta.fps) if camera.meta is not None and camera.meta.fps else 25
                streamer = create_rtsp_streamer(
                    output_rtsp_url,
                    width=preview_width,
                    height=preview_height,
                    fps=fps,
                )
                print(
                    f"[main] RTSP output started: {output_rtsp_url} "
                    f"({preview_width}x{preview_height} @ {fps} fps)"
                )

            packet = pipeline.process(packet)

            if streamer is not None:
                streamer.write(packet.resized_frame)

    finally:
        if streamer is not None:
            streamer.stop()
        camera.release()


if __name__ == "__main__":
    main()