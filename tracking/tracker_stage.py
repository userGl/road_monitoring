# tracker/tracker_stage.py
from __future__ import annotations

from core.frame_packet import FramePacket
from tracking.rdd_tracker import RDDTracker


class RDDTrackerStage:
    name = "rdd_tracker"

    def __init__(self, tracker: RDDTracker):
        self.tracker = tracker

    def __call__(self, packet: FramePacket) -> FramePacket:
        image = packet.frame

        tracked_detections, tracks, lost_events, shift = self.tracker.update(
            frame=image,
            detections=packet.detections,
            frame_id=packet.frame_id,
        )

        packet.detections = tracked_detections
        packet.tracks = tracks
        packet.lost_tracks = lost_events
        packet.motion = {
            "dx": round(shift.dx, 4),
            "dy": round(shift.dy, 4),
            "ok": shift.ok,
            "num_features": shift.num_features,
            "num_tracked": shift.num_tracked,
            "num_inliers": shift.num_inliers,
            "spread": round(shift.spread, 4),
            "reason": shift.reason,
        }
        return packet