# tracker/rdd_tracker.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
import math

import cv2
import numpy as np


BBox = Tuple[float, float, float, float]


@dataclass(slots=True)
class ShiftEstimate:
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

    predicted_bbox: Optional[BBox] = None
    history: deque = field(default_factory=lambda: deque(maxlen=5))

    def add_observation(self, frame_id: int, bbox: BBox, confidence: float) -> None:
        self.last_bbox = bbox
        self.last_confidence = confidence
        self.last_seen_frame = frame_id
        self.hit_count += 1
        self.miss_count = 0
        self.best_confidence = max(self.best_confidence, confidence)
        self.history.append(TrackObservation(frame_id=frame_id, bbox=bbox, confidence=confidence))

    def mark_missed(self) -> None:
        self.miss_count += 1

    @property
    def age(self) -> int:
        return max(0, self.last_seen_frame - self.created_frame + 1)


class RDDTracker:
    def __init__(
        self,
        confirm_hits: int = 3,
        max_misses: int = 3,
        min_match_score: float = 0.35,
        new_track_min_conf: float = 0.20,
        history_size: int = 5,
        use_motion_compensation: bool = True,
        debug: bool = False,
    ) -> None:
        self.confirm_hits = confirm_hits
        self.max_misses = max_misses
        self.min_match_score = min_match_score
        self.new_track_min_conf = new_track_min_conf
        self.history_size = history_size
        self.use_motion_compensation = use_motion_compensation
        self.debug = debug

        self.tracks: Dict[int, RDDTrack] = {}
        self.next_track_id = 1

        self.prev_gray: Optional[np.ndarray] = None
        self.last_shift = ShiftEstimate()

        self.w_iou = 0.45
        self.w_dist = 0.25
        self.w_scale = 0.20
        self.w_conf = 0.10

    def reset(self) -> None:
        self.tracks.clear()
        self.next_track_id = 1
        self.prev_gray = None
        self.last_shift = ShiftEstimate(reason="reset")

    def update(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        frame_id: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], ShiftEstimate]:
        
        gray = self._to_gray(frame)

        if self.use_motion_compensation:
            x1, y1, x2, y2 = self.get_motion_roi_rect(gray.shape[0], gray.shape[1])

            prev_roi = None
            if self.prev_gray is not None:
                prev_roi = self.prev_gray[y1:y2, x1:x2]

            curr_roi = gray[y1:y2, x1:x2]
            shift = self.estimate_global_shift(prev_roi, curr_roi)
        else:
            shift = ShiftEstimate(reason="motion_disabled")
        
        self.last_shift = shift

        for track in self.tracks.values():
            track.predicted_bbox = self.predict_bbox(track, shift, frame.shape)

        matches, unmatched_track_ids, unmatched_det_indices = self.match_detections(detections, frame.shape)

        for track_id, det_idx, score in matches:
            det = detections[det_idx]
            bbox = self._as_bbox(det["bbox"])
            conf = float(det.get("confidence", 0.0))
            track = self.tracks[track_id]
            track.add_observation(frame_id=frame_id, bbox=bbox, confidence=conf)
            if not track.confirmed and track.hit_count >= self.confirm_hits:
                track.confirmed = True

            det["track_id"] = track.track_id
            det["track_score"] = round(score, 4)
            det["is_new"] = (track.hit_count == self.confirm_hits)
            det["is_lost"] = False
            det["track_confirmed"] = track.confirmed

        for track_id in unmatched_track_ids:
            self.tracks[track_id].mark_missed()

        for det_idx in unmatched_det_indices:
            det = detections[det_idx]
            conf = float(det.get("confidence", 0.0))
            if conf < self.new_track_min_conf:
                det["track_id"] = None
                det["track_score"] = 0.0
                det["is_new"] = False
                det["is_lost"] = False
                det["track_confirmed"] = False
                continue

            bbox = self._as_bbox(det["bbox"])
            class_id = int(det.get("class_id", -1))
            class_name = str(det.get("class_name", "unknown"))
            track = self._create_track(
                class_id=class_id,
                class_name=class_name,
                bbox=bbox,
                confidence=conf,
                frame_id=frame_id,
            )

            det["track_id"] = track.track_id
            det["track_score"] = 0.0
            det["is_new"] = False
            det["is_lost"] = False
            det["track_confirmed"] = track.confirmed

        lost_events = []
        expired_ids = []
        for track_id, track in self.tracks.items():
            if track.miss_count > self.max_misses:
                lost_events.append(
                    {
                        "track_id": track.track_id,
                        "class_id": track.class_id,
                        "class_name": track.class_name,
                        "last_bbox": [round(v, 2) for v in track.last_bbox],
                        "best_confidence": round(track.best_confidence, 4),
                        "last_seen_frame": track.last_seen_frame,
                        "age": track.age,
                        "is_lost": True,
                    }
                )
                expired_ids.append(track_id)

        for track_id in expired_ids:
            del self.tracks[track_id]

        active_tracks = []
        for track in self.tracks.values():
            active_tracks.append(
                {
                    "track_id": track.track_id,
                    "class_id": track.class_id,
                    "class_name": track.class_name,
                    "bbox": [round(v, 2) for v in track.last_bbox],
                    "pred_bbox": [round(v, 2) for v in (track.predicted_bbox or track.last_bbox)],
                    "confidence": round(track.last_confidence, 4),
                    "best_confidence": round(track.best_confidence, 4),
                    "confirmed": track.confirmed,
                    "hit_count": track.hit_count,
                    "miss_count": track.miss_count,
                    "age": track.age,
                }
            )

        self.prev_gray = gray
        return detections, active_tracks, shift

    def get_motion_roi_rect(self, h: int, w: int) -> tuple[int, int, int, int]:
        x1 = int(w * 0.20)
        x2 = int(w * 0.80)
        y1 = int(h * 0.50)
        y2 = int(h * 0.85)

        x1 = max(0, min(x1, w - 1))
        x2 = max(x1 + 1, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(y1 + 1, min(y2, h))

        return x1, y1, x2, y2

    def estimate_global_shift(
        self,
        prev_gray: Optional[np.ndarray],
        curr_gray: np.ndarray,
    ) -> ShiftEstimate:
        if prev_gray is None:
            return ShiftEstimate(reason="no_prev_frame")

        if prev_gray.shape != curr_gray.shape:
            return ShiftEstimate(reason="shape_mismatch")

        features = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=200,
            qualityLevel=0.01,
            minDistance=10,
            blockSize=7,
        )
        if features is None:
            return ShiftEstimate(reason="no_features")

        num_features = len(features)
        if num_features < 20:
            return ShiftEstimate(num_features=num_features, reason="too_few_features")

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray,
            curr_gray,
            features,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )
        if next_pts is None or status is None:
            return ShiftEstimate(num_features=num_features, reason="lk_failed")

        status = status.reshape(-1).astype(bool)
        p0 = features.reshape(-1, 2)[status]
        p1 = next_pts.reshape(-1, 2)[status]

        num_tracked = len(p0)
        if num_tracked < 20:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                reason="too_few_tracked",
            )

        flow = p1 - p0
        dx_all = flow[:, 0]
        dy_all = flow[:, 1]
        mag = np.sqrt(dx_all**2 + dy_all**2)

        valid_mag = mag <= 60.0
        dx_all = dx_all[valid_mag]
        dy_all = dy_all[valid_mag]

        if len(dx_all) < 12:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                reason="too_few_after_mag_filter",
            )

        dx_med = float(np.median(dx_all))
        dy_med = float(np.median(dy_all))

        residual = np.sqrt((dx_all - dx_med) ** 2 + (dy_all - dy_med) ** 2)
        inliers = residual < 5.0
        num_inliers = int(np.sum(inliers))

        if num_inliers < 12:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                num_inliers=num_inliers,
                reason="too_few_inliers",
            )

        dx = float(np.median(dx_all[inliers]))
        dy = float(np.median(dy_all[inliers]))
        spread = float(np.median(residual[inliers])) if num_inliers > 0 else 9999.0

        if spread > 12.0:
            return ShiftEstimate(
                num_features=num_features,
                num_tracked=num_tracked,
                num_inliers=num_inliers,
                spread=spread,
                reason="spread_too_large",
            )

        dx = float(np.clip(dx, -30.0, 30.0))
        dy = float(np.clip(dy, -30.0, 30.0))

        if self.last_shift.ok:
            dx = 0.7 * dx + 0.3 * self.last_shift.dx
            dy = 0.7 * dy + 0.3 * self.last_shift.dy

        return ShiftEstimate(
            dx=dx,
            dy=dy,
            ok=True,
            num_features=num_features,
            num_tracked=num_tracked,
            num_inliers=num_inliers,
            spread=spread,
            reason="ok",
        )

    def predict_bbox(
        self,
        track: RDDTrack,
        shift: ShiftEstimate,
        frame_shape: Tuple[int, ...],
    ) -> BBox:
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = track.last_bbox

        dx = shift.dx if shift.ok else 0.0
        dy = shift.dy if shift.ok else 0.0

        pred = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        pred = self.clip_bbox(pred, w, h)

        if not self.is_valid_bbox(pred):
            return track.last_bbox
        return pred

    def match_detections(
        self,
        detections: List[Dict[str, Any]],
        frame_shape: Tuple[int, ...],
    ) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
        candidate_pairs: List[Tuple[float, int, int]] = []
        track_ids = list(self.tracks.keys())

        for track_id in track_ids:
            track = self.tracks[track_id]
            pred_bbox = track.predicted_bbox if track.predicted_bbox is not None else track.last_bbox

            for det_idx, det in enumerate(detections):
                det_class_id = int(det.get("class_id", -1))
                if det_class_id != track.class_id:
                    continue

                det_bbox = self._as_bbox(det["bbox"])

                gate_dist = self.max_match_distance(track.last_bbox)
                dist = self.center_distance(pred_bbox, det_bbox)
                if dist > gate_dist:
                    continue

                score = self.match_score(track, det_bbox, float(det.get("confidence", 0.0)))
                if score >= self.min_match_score:
                    candidate_pairs.append((score, track_id, det_idx))

        candidate_pairs.sort(key=lambda x: x[0], reverse=True)

        matched_tracks = set()
        matched_dets = set()
        matches: List[Tuple[int, int, float]] = []

        for score, track_id, det_idx in candidate_pairs:
            if track_id in matched_tracks or det_idx in matched_dets:
                continue
            matched_tracks.add(track_id)
            matched_dets.add(det_idx)
            matches.append((track_id, det_idx, score))

        unmatched_track_ids = [tid for tid in track_ids if tid not in matched_tracks]
        unmatched_det_indices = [i for i in range(len(detections)) if i not in matched_dets]

        return matches, unmatched_track_ids, unmatched_det_indices

    def match_score(self, track: RDDTrack, det_bbox: BBox, det_conf: float) -> float:
        pred_bbox = track.predicted_bbox if track.predicted_bbox is not None else track.last_bbox

        s_iou = self.compute_iou(pred_bbox, det_bbox)

        dist = self.center_distance(pred_bbox, det_bbox)
        dmax = self.max_match_distance(track.last_bbox)
        s_dist = max(0.0, 1.0 - (dist / max(dmax, 1e-6)))

        s_scale = self.area_ratio(track.last_bbox, det_bbox)
        s_conf = float(np.clip(det_conf, 0.0, 1.0))

        score = (
            self.w_iou * s_iou
            + self.w_dist * s_dist
            + self.w_scale * s_scale
            + self.w_conf * s_conf
        )
        return float(score)

    def max_match_distance(self, bbox: BBox) -> float:
        x1, y1, x2, y2 = bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        diag = math.sqrt(w * w + h * h)
        return 1.5 * diag

    def _create_track(
        self,
        class_id: int,
        class_name: str,
        bbox: BBox,
        confidence: float,
        frame_id: int,
    ) -> RDDTrack:
        track = RDDTrack(
            track_id=self.next_track_id,
            class_id=class_id,
            class_name=class_name,
            last_bbox=bbox,
            last_confidence=confidence,
            created_frame=frame_id,
            last_seen_frame=frame_id,
            hit_count=1,
            miss_count=0,
            confirmed=False,
            best_confidence=confidence,
            history=deque([TrackObservation(frame_id, bbox, confidence)], maxlen=self.history_size),
        )
        self.tracks[track.track_id] = track
        self.next_track_id += 1
        return track

    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _as_bbox(bbox_like: Any) -> BBox:
        x1, y1, x2, y2 = bbox_like
        return float(x1), float(y1), float(x2), float(y2)

    @staticmethod
    def center_distance(a: BBox, b: BBox) -> float:
        ax = (a[0] + a[2]) * 0.5
        ay = (a[1] + a[3]) * 0.5
        bx = (b[0] + b[2]) * 0.5
        by = (b[1] + b[3]) * 0.5
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    @staticmethod
    def area_ratio(a: BBox, b: BBox) -> float:
        area_a = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
        area_b = max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
        return float(min(area_a, area_b) / max(area_a, area_b))

    @staticmethod
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

    @staticmethod
    def clip_bbox(bbox: BBox, w: int, h: int) -> BBox:
        x1, y1, x2, y2 = bbox
        x1 = float(np.clip(x1, 0, w - 1))
        y1 = float(np.clip(y1, 0, h - 1))
        x2 = float(np.clip(x2, 0, w - 1))
        y2 = float(np.clip(y2, 0, h - 1))
        return x1, y1, x2, y2

    @staticmethod
    def is_valid_bbox(bbox: BBox) -> bool:
        x1, y1, x2, y2 = bbox
        return (x2 - x1) >= 2.0 and (y2 - y1) >= 2.0