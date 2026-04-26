# core/frame_packet.py
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
        model_input_frame: Кадр, подготовленный для подачи в модель.
        preprocess_meta: Служебная информация о предобработке кадра
            (режим, scale, padding и т.п.), если она выполнялась в пайплайне.
        detections: Список результатов детекции для кадра.
        tracks: Список треков / ассоциаций на текущем кадре.
        annotated_frame: Кадр с нанесёнными боксами, подписями и другой разметкой.
        meta: Произвольная служебная информация
            (например, путь до входного файла в images-режиме).
    """

    frame_id: int
    frame: np.ndarray
    ts_monotonic: float
    ts_wall: float

    model_input_frame: Optional[np.ndarray] = None
    preprocess_meta: Dict[str, Any] = field(default_factory=dict)

    # Детекции текущего кадра.
    # Базовые поля приходят из detector: bbox, confidence, class_id, class_name.
    # После tracker stage детекция может быть дополнена полями:
    # track_id, track_score, is_new, is_lost, track_confirmed.
    detections: List[Dict[str, Any]] = field(default_factory=list)

    # Треки на текущем кадре (агрегированная информация от трекера)
    tracks: List[Dict[str, Any]] = field(default_factory=list)

    # Информация о motion compensation / global shift
    motion: Dict[str, Any] = field(default_factory=dict)

    annotated_frame: Optional[np.ndarray] = None

    # Доп. служебные поля (input_path и т.п.)
    meta: Dict[str, Any] = field(default_factory=dict)