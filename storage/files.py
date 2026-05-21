from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

class FileStorage:
    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self.crops_dir = self.data_dir / "crops"
        self.crops_dir.mkdir(parents=True, exist_ok=True)

    def ensure_run_dir(self, run_id: int) -> Path:
        run_dir = self.crops_dir / f"run_{run_id:06d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def save_track_crop(
        self,
        crop: np.ndarray,
        run_id: int,
        track_id: int,
        class_name: str,
        frame_id: int | None = None,
        ext: str = ".jpg",
    ) -> str:
        run_dir = self.ensure_run_dir(run_id)

        if crop is None or crop.size == 0:
            raise ValueError("Empty crop image")

        suffix = f"_frame_{frame_id:06d}" if frame_id is not None else ""
        out_path = run_dir / f"track_{track_id:06d}{suffix}{ext}"

        ok = cv2.imwrite(str(out_path), crop)
        if not ok:
            raise IOError(f"Failed to save crop image to {out_path}")

        return str(out_path.relative_to(self.data_dir))

    def build_absolute_path(self, relative_path: str) -> Path:
        return self.data_dir / relative_path