# main.py Для начала пробуем запустить только RTSP preview и REST API
# main.py
import threading
import cv2
import uvicorn

from api.rest_api import app
from sensors.ffmpeg_camera import FFmpegRTSPCamera


def run_api():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        log_level="info",
    )


def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    rtsp_url = "rtsp://127.0.0.1:8554/live"
    camera = FFmpegRTSPCamera(rtsp_url, use_hwaccel=True)

    print("[main] RTSP preview started, API on :8081")

    meta_printed = False

    try:
        for packet in camera.frames():
            frame = packet.frame

            if not meta_printed and camera.meta is not None:
                print(f"[main] Video meta: {camera.meta}")
                meta_printed = True

           
            # if packet.frame_id % 30 == 0:
            #     print(
            #         f"[main] frame_id={packet.frame_id}, "
            #         f"ts_monotonic={packet.ts_monotonic:.6f}, "
            #         f"ts_wall={packet.ts_wall:.6f}"
            #     )

            if packet.frame_id % 2 == 0:
                cv2.imshow("RoadDamage RTSP", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    print("[main] ESC pressed, exiting...")
                    break

    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()