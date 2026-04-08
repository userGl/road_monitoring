# main.py Для начала пробуем запустить только RTSP preview и REST API
import threading
import cv2
import uvicorn

from api.rest_api import app
from sensors.camera import RTSPCamera


def run_api():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )


def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    rtsp_url = "rtsp://user:pass@192.168.1.10:554/stream"
    camera = RTSPCamera(rtsp_url)

    print("[main] RTSP preview started, API on :8080")

    try:
        for frame in camera.frames():
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
