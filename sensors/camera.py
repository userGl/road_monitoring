# sensors/camera.py
import time
from typing import Generator, Optional

import cv2
import numpy as np


class RTSPCamera:
    """
    Класс-обёртка над cv2.VideoCapture для RTSP-камеры
    с авто‑переподключением.
    """

    def __init__(
        self,
        rtsp_url: str,
        reconnect_delay: float = 5.0,
        read_timeout_sec: float = 5.0,
    ) -> None:
        """
        :param rtsp_url: RTSP URL камеры
        :param reconnect_delay: пауза перед попыткой переподключения (сек)
        :param read_timeout_sec: сколько секунд подряд можно не получать кадры
        """
        self.rtsp_url = rtsp_url
        self.reconnect_delay = reconnect_delay
        self.read_timeout_sec = read_timeout_sec

        self._cap: Optional[cv2.VideoCapture] = None
        self._last_ok_read_time: float = 0.0

def open(self) -> bool:
    """Открыть RTSP-поток."""
    self.release()

    # формируем URL с параметрами транспорта и буфера
    rtsp_url = (
        f"{self.rtsp_url}"
        "?rtsp_transport=tcp"
        "&max_delay=500000"
        "&buffer_size=1048576"
    )

    # Явно используем FFmpeg backend
    self._cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    ok = bool(self._cap and self._cap.isOpened())
    if ok:
        self._last_ok_read_time = time.time()
    else:
        print(f"[camera] failed to open RTSP stream: {rtsp_url}")
    return ok

    def release(self) -> None:
        """Освободить ресурс камеры."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _ensure_open(self) -> bool:
        """Проверить, что камера открыта, при необходимости попытаться открыть."""
        if self._cap is None or not self._cap.isOpened():
            return self.open()
        return True

    def read(self) -> Optional[np.ndarray]:
        """
        Прочитать один кадр.
        Возвращает np.ndarray (BGR) или None, если кадр недоступен.
        """
        if not self._ensure_open():
            # не удалось открыть стрим
            time.sleep(self.reconnect_delay)
            return None

        ret, frame = self._cap.read()
        now = time.time()

        if ret and frame is not None:
            self._last_ok_read_time = now
            return frame

        # нет кадра — проверяем, не завис ли поток
        if now - self._last_ok_read_time > self.read_timeout_sec:
            print("[camera] no frames for too long, reconnecting...")
            self.open()
        else:
            # кратковременный сбой — подождём немного
            time.sleep(0.05)

        return None

    def frames(self) -> Generator[np.ndarray, None, None]:
        """
        Бесконечный генератор кадров.
        Использовать в основном цикле:
            for frame in camera.frames():
                ...
        """
        try:
            while True:
                frame = self.read()
                if frame is None:
                    continue
                yield frame
        finally:
            self.release()


if __name__ == "__main__":
    # Простой тест модуля
    RTSP_URL = "rtsp://user:pass@host:554/stream"

    cam = RTSPCamera(RTSP_URL)

    for frame in cam.frames():
        cv2.imshow("rtsp", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break

    cam.release()
    cv2.destroyAllWindows()