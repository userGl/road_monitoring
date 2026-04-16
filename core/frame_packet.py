from dataclasses import dataclass, field
from typing import Optional, Any, Dict
import numpy as np


@dataclass(slots=True)
class VideoMeta:
    width: int
    height: int
    fps: float


@dataclass(slots=True)
class FramePacket:
    frame_id: int
    frame: np.ndarray
    ts_monotonic: float
    ts_wall: float

    resized_frame: Optional[np.ndarray] = None
    detections: list[Dict[str, Any]] = field(default_factory=list)
    annotated_frame: Optional[np.ndarray] = None
