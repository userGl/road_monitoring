# tracking/geometry.py
from __future__ import annotations

import math

import numpy as np

from .models import BBox


def center_distance(a: BBox, b: BBox) -> float:
    ax = (a[0] + a[2]) * 0.5
    ay = (a[1] + a[3]) * 0.5
    bx = (b[0] + b[2]) * 0.5
    by = (b[1] + b[3]) * 0.5
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def area_ratio(a: BBox, b: BBox) -> float:
    area_a = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
    return float(min(area_a, area_b) / max(area_a, area_b))


def compute_iou(a: BBox, b: BBox) -> float:
    x_left = max(a[0], b[0])
    y_top = max(a[1], b[1])
    x_right = min(a[2], b[2])
    y_bottom = min(a[3], b[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0.0

    inter = (x_right - x_left) * (y_bottom - y_top)
    area_a = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


def clip_bbox(bbox: BBox, w: int, h: int) -> BBox:
    x1, y1, x2, y2 = bbox
    x1 = float(np.clip(x1, 0, w - 1))
    y1 = float(np.clip(y1, 0, h - 1))
    x2 = float(np.clip(x2, 0, w - 1))
    y2 = float(np.clip(y2, 0, h - 1))
    return x1, y1, x2, y2


def is_valid_bbox(bbox: BBox) -> bool:
    x1, y1, x2, y2 = bbox
    return (x2 - x1) >= 2.0 and (y2 - y1) >= 2.0