# tracking/matching.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np

from .geometry import area_ratio, center_distance, compute_iou
from .models import BBox, RDDTrack


@dataclass(slots=True)
class TrackMatcher:
    min_match_score: float = 0.35
    w_iou: float = 0.45
    w_dist: float = 0.25
    w_scale: float = 0.20
    w_conf: float = 0.10

    def match_detections(
        self,
        tracks: Dict[int, RDDTrack],
        detections: List[Dict[str, Any]],
    ) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
        """Сопоставляет текущие детекции с активными треками.

        Для каждой пары «трек-детекция» вычисляется итоговый score.
        Затем пары сортируются по score и выбираются жадно, без повторного
        использования одного и того же трека или детекции.
        """
        candidate_pairs: List[Tuple[float, int, int]] = []
        track_ids = list(tracks.keys())

        # Кандидатные пары сначала отфильтровываются по class_id и расстоянию
        # между центрами до вычисления полного score. Это позволяет заранее
        # отсечь явно некорректные соответствия.
        for track_id in track_ids:
            track = tracks[track_id]
            pred_bbox = (
                track.predicted_bbox
                if track.predicted_bbox is not None
                else track.last_bbox
            )

            for det_idx, det in enumerate(detections):
                det_class_id = int(det.get("class_id", -1))
                if det_class_id != track.class_id:
                    continue

                det_bbox = self._as_bbox(det["bbox"])

                gate_dist = self.max_match_distance(track.last_bbox)
                dist = center_distance(pred_bbox, det_bbox)
                if dist > gate_dist:
                    continue

                score = self.match_score(
                    track,
                    det_bbox,
                    float(det.get("confidence", 0.0)),
                )
                if score >= self.min_match_score:
                    candidate_pairs.append((score, track_id, det_idx))

        candidate_pairs.sort(key=lambda x: x[0], reverse=True)

        matched_tracks = set()
        matched_dets = set()
        matches: List[Tuple[int, int, float]] = []

        # Жадного назначения здесь достаточно, потому что детекций немного,
        # а итоговый score уже учитывает геометрическую согласованность.
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
        """Вычисляет итоговый score сопоставления track ↔ detection.

        Score объединяет четыре фактора:
        - IoU между predicted_bbox и bbox детекции;
        - близость центров;
        - близость площади bbox;
        - уверенность (confidence) детекции.

        Чем больше score, тем правдоподобнее соответствие.
        """
        pred_bbox = (
            track.predicted_bbox
            if track.predicted_bbox is not None
            else track.last_bbox
        )

        s_iou = compute_iou(pred_bbox, det_bbox)

        dist = center_distance(pred_bbox, det_bbox)
        dmax = self.max_match_distance(track.last_bbox)
        s_dist = max(0.0, 1.0 - (dist / max(dmax, 1e-6)))

        s_scale = area_ratio(track.last_bbox, det_bbox)
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

    @staticmethod
    def _as_bbox(bbox_like: Any) -> BBox:
        x1, y1, x2, y2 = bbox_like
        return float(x1), float(y1), float(x2), float(y2)
