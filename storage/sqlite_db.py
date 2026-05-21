# storage/sqlite_db.py
from __future__ import annotations

import sqlite3
from pathlib import Path


def create_connection(db_path: str | Path = "data/events.db") -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS track_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,

            last_bbox_x1 REAL NOT NULL,
            last_bbox_y1 REAL NOT NULL,
            last_bbox_x2 REAL NOT NULL,
            last_bbox_y2 REAL NOT NULL,

            best_bbox_x1 REAL,
            best_bbox_y1 REAL,
            best_bbox_x2 REAL,
            best_bbox_y2 REAL,

            best_confidence REAL NOT NULL,
            best_frame_id INTEGER,
            last_seen_frame INTEGER NOT NULL,
            age INTEGER NOT NULL,
            confirmed INTEGER NOT NULL DEFAULT 1,

            position_meters REAL,
            crop_path TEXT,
            crop_width INTEGER,
            crop_height INTEGER,

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(run_id, track_id)
        )
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_results_run_track
        ON track_results(run_id, track_id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_track_results_class_name
        ON track_results(class_name)
        """
    )

    conn.commit()