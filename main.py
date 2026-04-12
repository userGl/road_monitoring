import threading
import uvicorn

from api.rest_api import app
from sensors.ffmpeg_camera import FFmpegRTSPCamera
from sensors.rtsp_streamer import RTSPStreamer, RTSPStreamerConfig


def run_api():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        log_level="info",
    )


def build_streamer(output_rtsp_url: str, camera_meta, frame):
    if camera_meta is not None:
        width = int(camera_meta.width)
        height = int(camera_meta.height)
        fps = int(camera_meta.fps) if camera_meta.fps else 25
    else:
        height, width = frame.shape[:2]
        fps = 25

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

    try:
        for packet in camera.frames():
            frame = packet.frame

            if not meta_printed and camera.meta is not None:
                print(f"[main] Video meta: {camera.meta}")
                meta_printed = True

            if streamer is None:
                streamer = build_streamer(output_rtsp_url, camera.meta, frame)

            if packet.frame_id % 1 == 0:
                streamer.write(frame)

    finally:
        if streamer is not None:
            streamer.stop()
        camera.release()


if __name__ == "__main__":
    main()