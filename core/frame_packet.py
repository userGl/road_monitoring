from dataclasses import dataclass, field
from typing import Optional, Any, Dict
import numpy as np


@dataclass(slots=True)
class VideoMeta:
    """Метаинформация о входном видеопотоке.

    Attributes:
        width: Ширина кадра в пикселях.
        height: Высота кадра в пикселях.
        fps: Частота кадров потока.
    """

    width: int
    height: int
    fps: float


@dataclass(slots=True)
class FramePacket:
    """Контейнер кадра и связанных данных для обработки в пайплайне.

    Attributes:
        frame_id: Порядковый номер кадра.
        frame: Исходный кадр в формате BGR.
        ts_monotonic: Монотонная временная метка для синхронизации.
        ts_wall: Системное время получения кадра.
        resized_frame: Кадр после ресайза, если он выполнялся в пайплайне.
        detections: Список результатов детекции для кадра.
        annotated_frame: Кадр с нанесёнными боксами, подписями и другой разметкой.
    """

    frame_id: int
    frame: np.ndarray
    ts_monotonic: float
    ts_wall: float

    resized_frame: Optional[np.ndarray] = None
    detections: list[Dict[str, Any]] = field(default_factory=list)
    annotated_frame: Optional[np.ndarray] = None