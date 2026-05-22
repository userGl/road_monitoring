# tracking/models.py
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Tuple, Optional

import numpy as np

BBox = Tuple[float, float, float, float]


@dataclass(slots=True)
class ShiftEstimate:
    """Оценка глобального межкадрового сдвига.

    Поля dx/dy описывают сдвиг камеры или фона между предыдущим и текущим
    кадром в пикселях. Оценка строится по оптическому потоку на ROI и затем
    используется для motion compensation при предсказании bbox треков.

    Если ok=False, трекер считает оценку недостоверной и не применяет сдвиг
    к track prediction.
    """
    dx: float = 0.0
    dy: float = 0.0
    ok: bool = False
    num_features: int = 0
    num_tracked: int = 0
    num_inliers: int = 0
    spread: float = 0.0
    reason: str = "init"


@dataclass(slots=True)
class TrackObservation:
    frame_id: int
    bbox: BBox
    confidence: float


@dataclass(slots=True)
class RDDTrack:
    """Состояние одного активного трека дефекта.

    Трек хранит последний bbox, confidence, историю наблюдений и служебные
    счётчики hit/miss. predicted_bbox — это прогноз позиции на текущем кадре
    после учёта motion compensation, а не подтверждённое наблюдение.
    """
    track_id: int
    class_id: int
    class_name: str
    last_bbox: BBox
    last_confidence: float
    created_frame: int
    last_seen_frame: int

    hit_count: int = 1
    miss_count: int = 0
    confirmed: bool = False
    best_confidence: float = 0.0

    best_bbox: Optional[BBox] = None
    best_frame_id: Optional[int] = None
    best_crop: Optional[np.ndarray] = None
    best_crop_shape: Optional[Tuple[int, int]] = None

    position_meters: Optional[float] = None
    saved_to_storage: bool = False

    predicted_bbox: Optional[BBox] = None
    history: deque = field(default_factory=lambda: deque(maxlen=5))

    def add_observation(self, frame_id: int, bbox: BBox, confidence: float) -> None:
        self.last_bbox = bbox
        self.last_confidence = confidence
        self.last_seen_frame = frame_id
        self.hit_count += 1
        self.miss_count = 0
        # self.best_confidence = max(self.best_confidence, confidence)
        self.history.append(
            TrackObservation(frame_id=frame_id, bbox=bbox, confidence=confidence)
        )

    def mark_missed(self) -> None:
        self.miss_count += 1

    @property
    def age(self) -> int:
        return max(0, self.last_seen_frame - self.created_frame + 1)