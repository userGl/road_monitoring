import logging
import shlex
import subprocess as sp
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class RTSPStreamerConfig:
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
    def __init__(self, config: RTSPStreamerConfig):
        self.cfg = config
        self.process: Optional[sp.Popen] = None
        self.lock = threading.Lock()
        self.running = False
        self.restart_count = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    def _build_ffmpeg_cmd(self) -> list[str]:
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
            cmd += [
                "-b:v", self.cfg.bitrate,
                "-maxrate", self.cfg.bitrate,
                "-bufsize", self.cfg.bitrate,
            ]

        cmd += [
            "-f", "rtsp",
            self.cfg.url,
        ]
        return cmd

    def start(self) -> None:
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.running = True
                return

            cmd = self._build_ffmpeg_cmd()
            self.logger.info("Starting FFmpeg RTSP publisher: %s", shlex.join(cmd))

            self.process = sp.Popen(
                cmd,
                stdin=sp.PIPE,
                stdout=sp.DEVNULL,
                stderr=sp.PIPE,
                bufsize=0,
            )
            self.running = True
            self.restart_count = 0

    def _restart(self) -> None:
        self.logger.warning("Restarting RTSP streamer...")
        self._stop_locked(wait=False)

        if self.restart_count >= self.cfg.max_restarts:
            raise RuntimeError(
                f"RTSP streamer exceeded max restarts: {self.cfg.max_restarts}"
            )

        self.restart_count += 1
        time.sleep(self.cfg.restart_backoff_sec)
        self.start()

    def _ensure_frame(self, frame: np.ndarray) -> np.ndarray:
        if frame is None:
            raise ValueError("Frame is None")

        if not isinstance(frame, np.ndarray):
            raise TypeError("Frame must be numpy.ndarray")

        if frame.dtype != np.uint8:
            raise ValueError(f"Frame dtype must be uint8, got {frame.dtype}")

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Frame must have shape (H, W, 3), got {frame.shape}"
            )

        h, w = frame.shape[:2]
        if (w, h) != (self.cfg.width, self.cfg.height):
            if not self.cfg.resize_if_needed:
                raise ValueError(
                    f"Invalid frame size {w}x{h}, "
                    f"expected {self.cfg.width}x{self.cfg.height}"
                )
            frame = cv2.resize(frame, (self.cfg.width, self.cfg.height))

        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        return frame

    def write(self, frame: np.ndarray) -> None:
        with self.lock:
            if not self.running:
                self.start()

            if self.process is None or self.process.stdin is None:
                self._restart()

            frame = self._ensure_frame(frame)

            try:
                self.process.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError) as e:
                self.logger.exception("FFmpeg pipe error: %s", e)
                self._restart()
                if self.process is None or self.process.stdin is None:
                    raise RuntimeError("Failed to restart RTSP streamer")
                self.process.stdin.write(frame.tobytes())

            if self.process.poll() is not None:
                err = b""
                if self.process.stderr is not None:
                    try:
                        err = self.process.stderr.read()
                    except Exception:
                        pass
                raise RuntimeError(
                    f"FFmpeg exited unexpectedly with code {self.process.returncode}. "
                    f"stderr: {err.decode('utf-8', errors='ignore')[:1000]}"
                )

    def _stop_locked(self, wait: bool = True) -> None:
        if self.process is None:
            self.running = False
            return

        try:
            if self.process.stdin:
                try:
                    self.process.stdin.close()
                except Exception:
                    pass

            if wait:
                try:
                    self.process.wait(timeout=5)
                except sp.TimeoutExpired:
                    self.logger.warning("FFmpeg did not exit in time, killing...")
                    self.process.kill()
                    self.process.wait(timeout=2)
            else:
                if self.process.poll() is None:
                    self.process.kill()
        finally:
            self.process = None
            self.running = False

    def stop(self) -> None:
        with self.lock:
            self._stop_locked(wait=True)

    def is_alive(self) -> bool:
        with self.lock:
            return self.process is not None and self.process.poll() is None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
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