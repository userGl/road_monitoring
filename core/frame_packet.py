from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List
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
        tracks: Список треков / ассоциаций на текущем кадре.
        annotated_frame: Кадр с нанесёнными боксами, подписями и другой разметкой.
        meta: Произвольная служебная информация (например, путь до входного файла в images-режиме).
    """

    frame_id: int
    frame: np.ndarray
    ts_monotonic: float
    ts_wall: float

    resized_frame: Optional[np.ndarray] = None

    # Детекции: можно оставить как list[dict], но договориться о ключах:
    # bbox, score, class_id, class_name, track_id, is_new, is_lost
    detections: List[Dict[str, Any]] = field(default_factory=list)

    # Треки на текущем кадре (агрегированная информация от трекера)
    tracks: List[Dict[str, Any]] = field(default_factory=list)

    annotated_frame: Optional[np.ndarray] = None

    # Доп. служебные поля (input_path и т.п.)
    meta: Dict[str, Any] = field(default_factory=dict)