# sensors/rtsp_streamer.py
import logging
import shlex
import subprocess as sp
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

@dataclass(slots=True)
class RTSPStreamerConfig:
    """Конфигурация RTSP-публикатора через ffmpeg.

    Хранит параметры входного raw video-потока, настройки кодирования,
    RTSP-транспорта и политики рестарта ffmpeg-процесса.
    """
    url: str
    width: int
    height: int
    fps: int = 25
    bitrate: str = "2M"
    codec: str = "libx264"
    preset: str = "veryfast"
    transport: str = "tcp"
    ffmpeg_bin: str = "ffmpeg"
    pix_fmt_in: str = "bgr24"
    pix_fmt_out: str = "yuv420p"
    gop: Optional[int] = None
    crf: Optional[int] = None
    max_restarts: int = 10
    restart_backoff_sec: float = 1.5
    loglevel: str = "error"
    resize_if_needed: bool = True


class RTSPStreamer:
    """Отправляет numpy-кадры в RTSP-поток через ffmpeg.

    Класс принимает BGR-кадры, при необходимости приводит их к нужному
    размеру и пишет в stdin ffmpeg-процесса, который публикует RTSP-поток.
    Поддерживает перезапуск ffmpeg при обрыве pipe.
    """

    def __init__(self, config: RTSPStreamerConfig):
        """Создаёт стример с заданной конфигурацией."""
        self.cfg = config
        self.process: Optional[sp.Popen] = None
        self.lock = threading.RLock()
        self.running = False
        self.restart_count = 0
        self.disabled = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def _build_ffmpeg_cmd(self) -> list[str]:
        """Собирает команду запуска ffmpeg для RTSP-публикации.

        На вход ffmpeg подаётся rawvideo из stdin, на выходе формируется
        RTSP-поток с заданным кодеком, FPS и параметрами битрейта/CRF.
        """
        gop = self.cfg.gop or self.cfg.fps
        cmd = [
            self.cfg.ffmpeg_bin,
            "-hide_banner",
            "-loglevel", self.cfg.loglevel,
            "-re",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-pix_fmt", self.cfg.pix_fmt_in,
            "-s", f"{self.cfg.width}x{self.cfg.height}",
            "-r", str(self.cfg.fps),
            "-i", "-",
            "-an",
            "-c:v", self.cfg.codec,
            "-preset", self.cfg.preset,
            "-tune", "zerolatency",
            "-pix_fmt", self.cfg.pix_fmt_out,
            "-g", str(gop),
            "-rtsp_transport", self.cfg.transport,
        ]

        if self.cfg.crf is not None:
            cmd += ["-crf", str(self.cfg.crf)]
        else:
            cmd += ["-b:v", self.cfg.bitrate, "-maxrate", self.cfg.bitrate, "-bufsize", self.cfg.bitrate]

        return cmd + ["-f", "rtsp", self.cfg.url]

    def _drain_stderr(self, proc: sp.Popen) -> None:
        """Читает stderr ffmpeg и отправляет строки в логгер.

        Нужен, чтобы pipe stderr не зависал из-за переполнения буфера
        и чтобы предупреждения ffmpeg были видны в логах приложения.
        """
        if proc.stderr is None:
            return
        for line in iter(proc.stderr.readline, b""):
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                self.logger.warning("[ffmpeg] %s", text)

    def _spawn_locked(self) -> None:
        """Запускает новый ffmpeg-процесс.

        Метод вызывается только под lock и создаёт subprocess с stdin для
        передачи кадров и отдельным потоком чтения stderr.
        """
        cmd = self._build_ffmpeg_cmd()
        self.logger.info("Starting FFmpeg RTSP publisher: %s", shlex.join(cmd))

        self.process = sp.Popen(
            cmd,
            stdin=sp.PIPE,
            stdout=sp.DEVNULL,
            stderr=sp.PIPE,
            bufsize=0,
        )

        threading.Thread(
            target=self._drain_stderr,
            args=(self.process,),
            daemon=True,
        ).start()

        self.running = True

    def start(self) -> None:
        """Запускает ffmpeg-публикатор, если он ещё не запущен."""
        with self.lock:
            if self.disabled:
                self.logger.warning("RTSP streamer is disabled; start() skipped")
                return

            if self.process is not None and self.process.poll() is None:
                self.running = True
                return

            self._spawn_locked()
            self.restart_count = 0

    def _restart_locked(self) -> None:
        """Перезапускает ffmpeg-процесс после ошибки записи или падения.

        Сбрасывает текущий процесс, ждёт небольшую паузу и запускает
        новый ffmpeg. Вызывается только под lock.
        """
        if self.restart_count >= self.cfg.max_restarts:
            self.logger.error(
                "RTSP streamer exceeded max restarts: %s. Disabling streamer.",
                self.cfg.max_restarts,
            )
            self.disabled = True
            self._stop_locked(wait=False)
            return

        self.logger.warning("Restarting RTSP streamer...")
        self.restart_count += 1
        self._stop_locked(wait=False)
        time.sleep(self.cfg.restart_backoff_sec)
        self._spawn_locked()

    def _ensure_frame(self, frame: np.ndarray) -> np.ndarray:
        """Проверяет и нормализует входной кадр.

        Гарантирует, что кадр имеет тип uint8, форму (H, W, 3), нужный
        размер и хранится в памяти сплошным блоком байт без «дыр» и 
        нестандартных шагов(strides) для безопасной передачи в ffmpeg.
        """
        if frame is None:
            raise ValueError("Frame is None")
        if not isinstance(frame, np.ndarray):
            raise TypeError("Frame must be numpy.ndarray")
        if frame.dtype != np.uint8:
            raise ValueError(f"Frame dtype must be uint8, got {frame.dtype}")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(f"Frame must have shape (H, W, 3), got {frame.shape}")

        h, w = frame.shape[:2]
        if (w, h) != (self.cfg.width, self.cfg.height):
            if not self.cfg.resize_if_needed:
                raise ValueError(
                    f"Invalid frame size {w}x{h}, expected {self.cfg.width}x{self.cfg.height}"
                )
            frame = cv2.resize(frame, (self.cfg.width, self.cfg.height))

        return frame if frame.flags["C_CONTIGUOUS"] else np.ascontiguousarray(frame)

    def _require_process_locked(self) -> None:
        """Гарантирует, что ffmpeg-процесс готов к записи.

        Если стример ещё не стартовал — запускает его.
        Если процесс умер или pipe недоступен — делает рестарт.
        """
        if self.disabled:
            return

        if not self.running:
            self.start()
        elif self.process is None or self.process.poll() is not None or self.process.stdin is None:
            self._restart_locked()

    def write(self, frame: np.ndarray) -> None:
        """Отправляет один кадр в ffmpeg stdin.

        При ошибке записи пытается один раз перезапустить ffmpeg и
        повторить отправку того же кадра. Если лимит рестартов исчерпан,
        стример отключается без падения основного приложения.
        """
        if self.disabled:
            return

        payload = self._ensure_frame(frame).tobytes()

        with self.lock:
            self._require_process_locked()

            if self.disabled:
                return

            try:
                assert self.process is not None and self.process.stdin is not None
                self.process.stdin.write(payload)
            except (BrokenPipeError, OSError) as e:
                self.logger.exception("FFmpeg pipe error: %s", e)
                self._restart_locked()

                if self.disabled:
                    return

                if self.process is None or self.process.stdin is None:
                    return

                self.process.stdin.write(payload)

            if self.process is not None and self.process.poll() is not None:
                self.logger.error(
                    "FFmpeg exited unexpectedly with code %s. Disabling streamer.",
                    self.process.returncode,
                )
                self.disabled = True
                self._stop_locked(wait=False)
                return     

    def _stop_locked(self, wait: bool = True) -> None:
        """Останавливает текущий ffmpeg-процесс и освобождает ресурсы.

        При wait=True пытается завершить процесс мягко, затем при необходимости
        делает kill. Вызывается под lock.
        """
        proc = self.process
        self.process = None
        self.running = False

        if proc is None:
            return

        try:
            if proc.stdin:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

            if wait:
                try:
                    proc.wait(timeout=5)
                except sp.TimeoutExpired:
                    self.logger.warning("FFmpeg did not exit in time, killing...")
                    proc.kill()
                    try:
                        proc.wait(timeout=2)
                    except sp.TimeoutExpired:
                        pass
            elif proc.poll() is None:
                proc.kill()
        finally:
            try:
                if proc.stderr:
                    proc.stderr.close()
            except Exception:
                pass

    def stop(self) -> None:
        """Останавливает стример и ffmpeg-процесс. """
        with self.lock:
            self._stop_locked(wait=True)

    def is_alive(self) -> bool:
        """Возвращает True, если ffmpeg-процесс сейчас жив."""
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def is_disabled(self) -> bool:
        """Возвращает True, если стример отключён после ошибок."""
        with self.lock:
            return self.disabled

    def __enter__(self):
        """Поддержка with: при входе запустить стример."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Поддержка with: при выходе остановить стример."""
        self.stop()

def create_rtsp_streamer(
    url: str,
    width: int,
    height: int,
    fps: int = 25,
    *,
    bitrate: str = "2M",
    preset: str = "veryfast",
    transport: str = "tcp",
    resize_if_needed: bool = True,
) -> RTSPStreamer:
    """Функция для создания и запуска RTSPStreamer."""
    cfg = RTSPStreamerConfig(
        url=url,
        width=width,
        height=height,
        fps=fps,
        bitrate=bitrate,
        preset=preset,
        transport=transport,
        resize_if_needed=resize_if_needed,
    )
    streamer = RTSPStreamer(cfg)
    streamer.start()
    return streamer