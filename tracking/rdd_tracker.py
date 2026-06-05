from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from .geometry import clip_bbox, is_valid_bbox
from .matching import TrackMatcher
from .models import BBox, RDDTrack, ShiftEstimate, TrackObservation
from .motion import MotionEstimator

class RDDTracker:
    """Лёгкий multi-object tracker для дефектов дороги.


    Трекер сопоставляет детекции между кадрами по комбинации IoU, расстояния
    между центрами, близости масштаба и confidence. При включённой
    motion compensation он сначала оценивает глобальный сдвиг кадра по LK
    optical flow на ROI, а затем сдвигает bbox существующих треков перед
    matching.
    """
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

        self.prev_gray: np.ndarray | None = None
        self.last_shift = ShiftEstimate()

        self.motion = MotionEstimator()
        self.matcher = TrackMatcher(min_match_score=min_match_score)

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
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], ShiftEstimate]:
        """Обновляет трекер по новому кадру и текущим детекциям.

        На каждом шаге:
        1. Оценивается глобальный сдвиг кадра.
        2. Прогнозируется положение активных треков.
        3. Выполняется сопоставление треков и детекций.
        4. Обновляются существующие треки и создаются новые.
        5. Удаляются треки, превысившие допустимое число пропусков.
        """
        
        # Для оценки глобального движения достаточно градаций серого:
        gray = self._to_gray(frame)

        if self.use_motion_compensation:
        # Оптический поток считается не по всему кадру, а только по ROI,
            x1, y1, x2, y2 = self.motion.get_motion_roi_rect(gray.shape[0], gray.shape[1])

            prev_roi = None
            if self.prev_gray is not None:
                prev_roi = self.prev_gray[y1:y2, x1:x2]

            curr_roi = gray[y1:y2, x1:x2]
            shift = self.motion.estimate_global_shift(prev_roi, curr_roi, last_shift=self.last_shift)
        else:
            shift = ShiftEstimate(reason="motion_disabled")

        self.last_shift = shift
        # predicted_bbox используется только как прогноз положения трека
        # на текущем кадре перед этапом matching.
        for track in self.tracks.values():
            track.predicted_bbox = self.predict_bbox(track, shift, frame.shape)
        # Сопоставление выполняется с учётом класса объекта:
        # детекция сравнивается только с треками того же class_id.
        matches, unmatched_track_ids, unmatched_det_indices = self.matcher.match_detections(
            self.tracks,
            detections,
        )
        # Для совпавших пар обновляем треки реальными наблюдениями от детектора.
        for track_id, det_idx, score in matches:
            det = detections[det_idx]
            bbox = self._as_bbox(det["bbox"])
            conf = float(det.get("confidence", 0.0))
            track = self.tracks[track_id]
            track.add_observation(frame_id=frame_id, bbox=bbox, confidence=conf)
            self._update_best_observation(
                track=track,
                frame=frame,
                frame_id=frame_id,
                bbox=bbox,
                confidence=conf,
            )
            # Если трек ещё не подтверждён, но набрал достаточно наблюдений,
            # то подтверждаем его.
            if not track.confirmed and track.hit_count >= self.confirm_hits:
                track.confirmed = True

            det["track_id"] = track.track_id
            det["track_score"] = round(score, 4)
            det["is_new"] = (track.hit_count == self.confirm_hits)
            det["is_lost"] = False
            det["track_confirmed"] = track.confirmed
        # Несопоставленные треки не удаляются сразу:
        # сначала для них увеличивается счётчик пропусков.
        for track_id in unmatched_track_ids:
            self.tracks[track_id].mark_missed()
        # Несопоставленные детекции могут породить новые треки,
        # если confidence достаточно высокий.
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
                frame=frame,
            )

            det["track_id"] = track.track_id
            det["track_score"] = 0.0
            det["is_new"] = False
            det["is_lost"] = False
            det["track_confirmed"] = track.confirmed
        # Треки удаляются только после превышения max_misses,
        # чтобы переживать кратковременные пропуски детектора.
        lost_events = []
        expired_ids = []
        for track_id, track in self.tracks.items():
            if track.miss_count > self.max_misses:
                if track.confirmed:
                    lost_events.append(
                        {
                            "track_id": track.track_id,
                            "class_id": track.class_id,
                            "class_name": track.class_name,
                            "last_bbox": [round(v, 2) for v in track.last_bbox],
                            "best_bbox": [round(v, 2) for v in track.best_bbox] if track.best_bbox else None,
                            "best_confidence": round(track.best_confidence, 4),
                            "best_frame_id": track.best_frame_id,
                            "best_crop": track.best_crop,
                            "best_crop_shape": list(track.best_crop_shape) if track.best_crop_shape else None,
                            "last_seen_frame": track.last_seen_frame,
                            "age": track.age,
                            "saved_to_storage": track.saved_to_storage,
                            "confirmed": track.confirmed,
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
                    "best_bbox": [round(v, 2) for v in track.best_bbox] if track.best_bbox else None,
                    "best_frame_id": track.best_frame_id,
                    "has_best_crop": track.best_crop is not None,
                    "confirmed": track.confirmed,
                    "hit_count": track.hit_count,
                    "miss_count": track.miss_count,
                    "age": track.age,
                }
            )
        # Сохраняем текущий grayscale-кадр для оценки optical flow
        # на следующем шаге обновлени
        self.prev_gray = gray
        return detections, active_tracks, lost_events, shift


    def predict_bbox(
        self,
        track: RDDTrack,
        shift: ShiftEstimate,
        frame_shape: Tuple[int, ...],
    ) -> BBox:
        """Строит прогноз bbox на текущем кадре.

        К последнему bbox прибавляется глобальный shift кадра.
        """
        h, w = frame_shape[:2]
        x1, y1, x2, y2 = track.last_bbox

        dx = shift.dx if shift.ok else 0.0
        dy = shift.dy if shift.ok else 0.0

        pred = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
        pred = clip_bbox(pred, w, h)

        if not is_valid_bbox(pred):
            return track.last_bbox
        return pred

    def _create_track(
        self,
        class_id: int,
        class_name: str,
        bbox: BBox,
        confidence: float,
        frame_id: int,
        frame: np.ndarray,
    ) -> RDDTrack:
        crop = self._extract_crop(frame, bbox)

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
            best_bbox=bbox,
            best_frame_id=frame_id,
            best_crop=crop,
            best_crop_shape=(crop.shape[:2] if crop is not None else None),
            history=deque(
                [TrackObservation(frame_id, bbox, confidence)],
                maxlen=self.history_size,
            ),
        )
        self.tracks[track.track_id] = track
        self.next_track_id += 1
        return track


    def _update_best_observation(
        self,
        track: RDDTrack,
        frame: np.ndarray,
        frame_id: int,
        bbox: BBox,
        confidence: float,
    ) -> None:
        if confidence < track.best_confidence and track.best_bbox is not None:
            return

        crop = self._extract_crop(frame, bbox)
        if crop is None:
            return

        track.best_confidence = confidence
        track.best_bbox = bbox
        track.best_frame_id = frame_id
        track.best_crop = crop
        track.best_crop_shape = crop.shape[:2]


    @staticmethod
    def _extract_crop(frame: np.ndarray, bbox: BBox) -> np.ndarray | None:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(int, bbox)

        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        return crop.copy()


    @staticmethod
    def _to_gray(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return frame
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _as_bbox(bbox_like: Any) -> BBox:
        x1, y1, x2, y2 = bbox_like
        return float(x1), float(y1), float(x2), float(y2)