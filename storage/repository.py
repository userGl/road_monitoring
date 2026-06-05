from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

BBox = Tuple[float, float, float, float]


@dataclass(slots=True)
class TrackResultRecord:
    run_id: int
    track_id: int
    class_id: int
    class_name: str
    last_bbox: BBox
    best_bbox: Optional[BBox]
    best_confidence: float
    best_frame_id: Optional[int]
    last_seen_frame: int
    age: int
    confirmed: bool = True
    crop_path: Optional[str] = None
    crop_width: Optional[int] = None
    crop_height: Optional[int] = None


class TrackResultRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def save_track_result(self, record: TrackResultRecord) -> None:
        last_x1, last_y1, last_x2, last_y2 = record.last_bbox

        if record.best_bbox is not None:
            best_x1, best_y1, best_x2, best_y2 = record.best_bbox
        else:
            best_x1 = best_y1 = best_x2 = best_y2 = None

        self.conn.execute(
            """
            INSERT INTO track_results (
                run_id,
                track_id,
                class_id,
                class_name,
                last_bbox_x1,
                last_bbox_y1,
                last_bbox_x2,
                last_bbox_y2,
                best_bbox_x1,
                best_bbox_y1,
                best_bbox_x2,
                best_bbox_y2,
                best_confidence,
                best_frame_id,
                last_seen_frame,
                age,
                confirmed,
                crop_path,
                crop_width,
                crop_height
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, track_id) DO UPDATE SET
                class_id = excluded.class_id,
                class_name = excluded.class_name,
                last_bbox_x1 = excluded.last_bbox_x1,
                last_bbox_y1 = excluded.last_bbox_y1,
                last_bbox_x2 = excluded.last_bbox_x2,
                last_bbox_y2 = excluded.last_bbox_y2,
                best_bbox_x1 = excluded.best_bbox_x1,
                best_bbox_y1 = excluded.best_bbox_y1,
                best_bbox_x2 = excluded.best_bbox_x2,
                best_bbox_y2 = excluded.best_bbox_y2,
                best_confidence = excluded.best_confidence,
                best_frame_id = excluded.best_frame_id,
                last_seen_frame = excluded.last_seen_frame,
                age = excluded.age,
                confirmed = excluded.confirmed,
                crop_path = excluded.crop_path,
                crop_width = excluded.crop_width,
                crop_height = excluded.crop_height
            """,
            (
                record.run_id,
                record.track_id,
                record.class_id,
                record.class_name,

                last_x1,
                last_y1,
                last_x2,
                last_y2,

                best_x1,
                best_y1,
                best_x2,
                best_y2,

                record.best_confidence,
                record.best_frame_id,
                record.last_seen_frame,
                record.age,
                int(record.confirmed),
                record.crop_path,
                record.crop_width,
                record.crop_height,
            ),
        )
        self.conn.commit()

    def get_track_result(self, run_id: int, track_id: int):
        cur = self.conn.execute(
            """
            SELECT *
            FROM track_results
            WHERE run_id = ? AND track_id = ?
            """,
            (run_id, track_id),
        )
        return cur.fetchone()