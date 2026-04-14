import json
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Generator, Optional, Any, Dict

import numpy as np
from subprocess import CalledProcessError


@dataclass
class VideoMeta:
    """Метаинформация о видеопотоке.

    Хранит исходные параметры RTSP-потока, полученные через ffprobe:
    разрешение (width/height) и номинальный FPS.
    """
    width: int
    height: int
    fps: float

@dataclass
class FramePacket:
    """Пакет кадра с метаданными.

    Обёртка над numpy-кадром, содержит:
    - frame_id: сквозной порядковый номер кадра;
    - frame: сам кадр в формате BGR (H x W x 3);
    - ts_monotonic: время получения кадра (time.monotonic);
    - ts_wall: «часы реального мира» (time.time) для логов/БД.

    - resized_frame: картинка с измененным размером для модели
    - detections: список детекций
    - annotated_frame: картинка с отмеченными детекциями
    """
    frame_id: int
    frame: np.ndarray
    ts_monotonic: float
    ts_wall: float

    resized_frame: Optional[np.ndarray] = None
    detections: list[Dict[str, Any]] = field(default_factory=list)
    annotated_frame: Optional[np.ndarray] = None

class FFmpegRTSPCamera:
    """Захват RTSP-потока через ffmpeg с авто-реконнектом.

    Оборачивает ffprobe/ffmpeg в класс камеры:
    - пробует получить метаданные потока через ffprobe;
    - запускает ffmpeg с опциональным аппаратным декодированием;
    - отдаёт кадры как FramePacket через генератор frames().
    """

    def __init__(
        self,
        rtsp_url: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[float] = None,
        reconnect_delay: float = 2.0,
        max_bad_reads: int = 10,
        use_hwaccel: bool = False,
    ) -> None:
        """Инициализация камеры.

        rtsp_url        – URL RTSP-потока.
        reconnect_delay – пауза между попытками переподключения.
        max_bad_reads   – сколько подряд неудачных чтений ждем до рестарта ffmpeg.
        use_hwaccel     – использовать ли CUDA-ускорение декодирования.
        """
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.meta: Optional[VideoMeta] = None

        self.proc: Optional[subprocess.Popen] = None
        self._frame_size: Optional[int] = None
        self.reconnect_delay = reconnect_delay
        self.max_bad_reads = max_bad_reads
        self.use_hwaccel = use_hwaccel

        self._bad_reads = 0
        self._frame_id = 0

    def _parse_fps(self, value: str) -> float:
        """Разбирает FPS из строки ffprobe (вида '25/1' или '30').

        Возвращает FPS в виде float, для некорректных значений
        подставляет разумное значение по умолчанию (25.0).
        """
        if not value or value == "0/0":
            return 25.0
        if "/" in value:
            num, den = value.split("/", 1)
            num = float(num)
            den = float(den)
            if den == 0:
                return 25.0
            return num / den
        return float(value)

    def _probe_video_meta(self) -> VideoMeta:
        """Вызывает ffprobe и вытаскивает width/height/FPS.

        Запускает ffprobe для первого видеопотока (v:0),
        парсит JSON-ответ, возвращает VideoMeta.
        При ошибках сети/RTSP или таймауте бросает RuntimeError.
        """
        cmd = (
            f'ffprobe -v error '
            f'-select_streams v:0 '
            f'-show_entries stream=width,height,avg_frame_rate,r_frame_rate '
            f'-of json '
            f'{shlex.quote(self.rtsp_url)}'
        )

        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
        except CalledProcessError as e:
            msg = (e.stderr or e.stdout or "").strip()
            print(f"[camera] ffprobe failed for {self.rtsp_url}: {msg}", file=sys.stderr)
            raise RuntimeError("ffprobe failed") from e
        except subprocess.TimeoutExpired:
            print(f"[camera] ffprobe timeout for {self.rtsp_url}", file=sys.stderr)
            raise RuntimeError("ffprobe timeout")

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if not streams:
            raise RuntimeError("No video stream found")

        stream = streams[0]
        width = int(stream["width"])
        height = int(stream["height"])
        fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "25/1"
        fps = self._parse_fps(fps_raw)

        return VideoMeta(width=width, height=height, fps=fps)

    def open(self) -> None:
        """Открывает RTSP-поток (поднимает ffmpeg-процесс).

        Если процесс уже жив – ничего не делает.
        Иначе:
        - через ffprobe получает метаинформацию потока;
        - запускает ffmpeg (с hwaccel или без) и поток логирования stderr.
        При ошибках ffprobe логирует и оставляет камеру в «закрытом» состоянии.
        """
        if self.proc is not None and self.proc.poll() is None:
            return

        self.release()

        try:
            self.meta = self._probe_video_meta()
        except RuntimeError as e:
            print(f"[camera] open failed: {e}", file=sys.stderr)
            self.meta = None
            return

        self.width = self.meta.width
        self.height = self.meta.height
        self.fps = self.meta.fps

        self._frame_size = self.width * self.height * 3

        if self.use_hwaccel:
            cmd = (
                f'ffmpeg -loglevel warning '
                f'-rtsp_transport tcp '
                f'-hwaccel cuda -hwaccel_output_format cuda '
                f'-i {shlex.quote(self.rtsp_url)} '
                f'-vf hwdownload,format=nv12,format=bgr24 '
                f'-f rawvideo -pix_fmt bgr24 -'
            )
        else:
            cmd = (
                f'ffmpeg -loglevel warning '
                f'-rtsp_transport tcp '
                f'-i {shlex.quote(self.rtsp_url)} '
                f'-f rawvideo -pix_fmt bgr24 -'
            )

        self.proc = subprocess.Popen(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=self._frame_size * 2,
        )

        threading.Thread(target=self._log_stderr, args=(self.proc,), daemon=True).start()

        mode = "cuda" if self.use_hwaccel else "cpu"
        print(
            f"[camera] connected: {self.width}x{self.height}, "
            f"fps={self.fps:.3f}, decode={mode}"
        )

    def _log_stderr(self, proc: subprocess.Popen) -> None:
        """Читает stderr ffmpeg и прокидывает строки в общий stderr.

        Запускается в отдельном потоке, чтобы не блокировать чтение stdout.
        Позволяет видеть предупреждения/ошибки ffmpeg в логах Python-приложения.
        """
        assert proc.stderr is not None
        for line in proc.stderr:
            try:
                line = line.decode("utf-8", errors="replace").strip()
            except Exception:
                continue
            if line:
                print(f"[ffmpeg] {line}", file=sys.stderr)

    def release(self) -> None:
        """Корректно завершает ffmpeg-процесс и сбрасывает счётчики.

        Пытается послать terminate() с таймаутом,
        при необходимости делает kill(), обнуляет self.proc и _bad_reads.
        Вызывать при выходе или ошибках, когда поток больше не нужен.
        """
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
            self.proc = None
        self._bad_reads = 0

    def read(self) -> Optional[FramePacket]:
        """Читает один кадр из stdout ffmpeg и заворачивает его в FramePacket.

        При успешном чтении полного кадра:
        - сбрасывает счётчик _bad_reads;
        - создаёт numpy-массив кадра и ставит временные метки;
        - возвращает FramePacket.

        При частичном/пустом чтении увеличивает _bad_reads, логирует аномалии
        и возвращает None. Не занимается переподключением – это делает frames().
        """
        if self.proc is None or self.proc.poll() is not None:
            return None

        assert self.proc is not None
        assert self.proc.stdout is not None
        assert self._frame_size is not None
        assert self.width is not None and self.height is not None

        data = self.proc.stdout.read(self._frame_size)
        if len(data) == self._frame_size:
            self._bad_reads = 0
            frame = np.frombuffer(data, np.uint8).reshape((self.height, self.width, 3)).copy()

            packet = FramePacket(
                frame_id=self._frame_id,
                frame=frame,
                ts_monotonic=time.monotonic(),
                ts_wall=time.time(),
            )
            self._frame_id += 1
            return packet

        self._bad_reads += 1
        if 0 < len(data) < self._frame_size:
            print(
                f'[camera] short read: got {len(data)} bytes, '
                f'expected {self._frame_size}, bad_reads={self._bad_reads}',
                file=sys.stderr,
            )

        if len(data) == 0 and self.proc.poll() is not None:
            print('[camera] ffmpeg process exited', file=sys.stderr)
            return None

        if len(data) == 0 and self.proc.poll() is None:
            print(
                f'[camera] empty read, bad_reads={self._bad_reads}',
                file=sys.stderr,
            )

        return None

    def frames(self) -> Generator[FramePacket, None, None]:
        """Генератор непрерывной последовательности кадров с авто-реконнектом.

        Бесконечно:
        - следит за состоянием ffmpeg-процесса;
        - при падении/отсутствии потока пытается переподключиться с паузой;
        - читает кадры через read() и отдаёт только валидные FramePacket.

        При превышении max_bad_reads подряд перезапускает ffmpeg.
        Гарантированно вызывает release() при выходе из генератора.
        """
        try:
            while True:
                if self.proc is None or self.proc.poll() is not None:
                    print('[camera] stream lost, reconnecting...', file=sys.stderr)
                    time.sleep(self.reconnect_delay)
                    try:
                        self.open()
                    except Exception as e:
                        print(f'[camera] reconnect failed: {e}', file=sys.stderr)
                        time.sleep(self.reconnect_delay)
                        continue

                    # важно: open() могла не поднять ffmpeg, если потока нет
                    if self.proc is None:
                        # ждём следующей попытки
                        continue

                frame = self.read()
                if frame is None:
                    if self._bad_reads >= self.max_bad_reads:
                        print(
                            f'[camera] too many bad reads ({self._bad_reads}), restarting ffmpeg...',
                            file=sys.stderr,
                        )
                        self.release()
                        self._bad_reads = 0
                        time.sleep(self.reconnect_delay)
                    continue

                yield frame
        finally:
            self.release()