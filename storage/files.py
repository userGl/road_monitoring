# storage/files.py
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

BBox = Tuple[float, float, float, float]


class FileStorage:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.crops_dir = self.data_dir / "crops"
        self.crops_dir.mkdir(parents=True, exist_ok=True)

    def ensure_run_dir(self, run_id: int) -> Path:
        run_dir = self.crops_dir / f"run_{run_id:06d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_crop_image(
        self,
        frame: np.ndarray,
        bbox: BBox,
        run_id: int,
        track_id: int,
        ext: str = ".jpg",
    ) -> str:
        run_dir = self.ensure_run_dir(run_id)

        x1, y1, x2, y2 = map(int, bbox)
        h, w = frame.shape[:2]

        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Invalid bbox for crop: {(x1, y1, x2, y2)}")

        crop = frame[y1:y2, x1:x2]
        out_path = run_dir / f"track_{track_id:06d}{ext}"

        ok = cv2.imwrite(str(out_path), crop)
        if not ok:
            raise IOError(f"Failed to save crop image to {out_path}")

        return str(out_path.relative_to(self.data_dir))

    def build_absolute_path(self, relative_path: str) -> Path:
        return self.data_dir / relative_path