from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import cv2
import time

from core.frame_packet import FramePacket, VideoMeta


class ImageFolderCamera:
    """Источник кадров из папки с изображениями для тестового режима.

    Имитирует видеопоток с заданным FPS:
    - читает картинки из папки в алфавитном порядке;
    - на каждый файл создаёт FramePacket с корректным frame_id и таймстемпами;
    - выдаёт кадры через frames() подобно FFmpegRTSPCamera.frames().
    """

    def __init__(self, input_dir: str, fps: int = 5) -> None:
        self.input_dir = Path(input_dir)
        self.fps = max(fps, 1)

        if not self.input_dir.exists() or not self.input_dir.is_dir():
            raise ValueError(f"Images directory does not exist or is not a directory: {self.input_dir}")

        # Собираем список файлов один раз при инициализации
        self._image_files: List[Path] = sorted(
            [
                p
                for p in self.input_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
        )
        if not self._image_files:
            raise ValueError(f"No images found in directory: {self.input_dir}")

        # Инициализируем meta после чтения первого кадра (узнаем width/height)
        first_img = cv2.imread(str(self._image_files[0]))
        if first_img is None:
            raise RuntimeError(f"Failed to read first image: {self._image_files[0]}")

        height, width = first_img.shape[:2]
        self.meta: Optional[VideoMeta] = VideoMeta(width=width, height=height, fps=float(self.fps))

        # Временные базовые отметки, чтобы ts_monotonic/ts_wall были согласованы с fps
        self._t0_monotonic = time.monotonic()
        self._t0_wall = time.time()

    def frames(self) -> Iterable[FramePacket]:
        """Генератор кадров как последовательности FramePacket.

        Для каждого изображения из папки:
        - читает файл;
        - формирует таймстемпы как t0 + frame_id / fps;
        - заполняет FramePacket (frame, frame_id, ts_*);
        - кладёт в meta путь до входного файла и fps.
        """
        frame_interval = 1.0 / float(self.fps)

        for frame_id, img_path in enumerate(self._image_files):
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"[ImageFolderCamera] failed to read image: {img_path}")
                continue

            # Если размер отличается от первого кадра, можно просто обновить meta или оставить как есть.
            h, w = image.shape[:2]
            if self.meta and (w != self.meta.width or h != self.meta.height):
                # Не трогаю self.meta, чтобы не ломать ожидания,
                # но при желании можно логировать.
                print(
                    f"[ImageFolderCamera] warning: image size {w}x{h} "
                    f"differs from meta {self.meta.width}x{self.meta.height}"
                )

            ts_monotonic = self._t0_monotonic + frame_id * frame_interval
            ts_wall = self._t0_wall + frame_id * frame_interval

            packet = FramePacket(
                frame_id=frame_id,
                frame=image,
                ts_monotonic=ts_monotonic,
                ts_wall=ts_wall,
            )
            packet.meta["input_path"] = str(img_path)
            packet.meta["fps"] = self.fps

            yield packet

            # При желании можно симулировать реальное время:
            # time.sleep(frame_interval)

    def release(self) -> None:
        """Для совместимости с интерфейсом FFmpegRTSPCamera."""
        # Нечего освобождать, но метод нужен, чтобы main() не различал источники.
        pass