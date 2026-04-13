# main.py
import threading
import uvicorn

from api.rest_api import app
from sensors.ffmpeg_camera import FFmpegRTSPCamera
from sensors.rtsp_streamer import RTSPStreamer, RTSPStreamerConfig

from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage


PREVIEW_WIDTH = 640
PREVIEW_HEIGHT = 640


def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


def build_streamer(output_rtsp_url: str, width: int, height: int, fps: int = 25):
    streamer = RTSPStreamer(
        RTSPStreamerConfig(
            url=output_rtsp_url,
            width=width,
            height=height,
            fps=fps,
            bitrate="2M",
            preset="veryfast",
            transport="tcp",
            resize_if_needed=True,
        )
    )
    streamer.start()

    print(
        f"[main] RTSP output started: {output_rtsp_url} "
        f"({width}x{height} @ {fps} fps)"
    )
    return streamer


def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    input_rtsp_url = "rtsp://127.0.0.1:8554/live"
    output_rtsp_url = "rtsp://127.0.0.1:8554/preview"

    camera = FFmpegRTSPCamera(input_rtsp_url, use_hwaccel=True)
    print("[main] RTSP input started, API on :8081")

    meta_printed = False
    streamer = None
    pipeline = None

    try:
        for packet in camera.frames():
            frame = packet.frame

            if not meta_printed and camera.meta is not None:
                print(f"[main] Video meta: {camera.meta}")
                meta_printed = True

            if pipeline is None:
                pipeline = VideoPipeline(
                    stages=[
                        ResizeStage(width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT),
                    ]
                )

            if streamer is None:
                fps = int(camera.meta.fps) if camera.meta is not None and camera.meta.fps else 25
                streamer = build_streamer(
                    output_rtsp_url,
                    width=PREVIEW_WIDTH,
                    height=PREVIEW_HEIGHT,
                    fps=fps,
                )

            packet = pipeline.process(packet)

            # Пока в preview отдаём кадр после resize
            streamer.write(packet.resized_frame)

    finally:
        if streamer is not None:
            streamer.stop()
        camera.release()


if __name__ == "__main__":
    main()