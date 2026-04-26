# pipeline/stages.py
from typing import Protocol
import cv2

from core.frame_packet import FramePacket
from inference.yolo_detector import YoloDetector


class Stage(Protocol):
    name: str

    def __call__(self, packet: FramePacket) -> FramePacket:
        ...


def map_bbox_to_original(bbox, preprocess_meta: dict) -> list[int]:
    x1, y1, x2, y2 = bbox

    scale_x = float(preprocess_meta["scale_x"])
    scale_y = float(preprocess_meta["scale_y"])
    roi_x = int(preprocess_meta["roi_x"])
    roi_y = int(preprocess_meta["roi_y"])
    src_w = int(preprocess_meta["src_width"])
    src_h = int(preprocess_meta["src_height"])

    x1 = x1 * scale_x + roi_x
    y1 = y1 * scale_y + roi_y
    x2 = x2 * scale_x + roi_x
    y2 = y2 * scale_y + roi_y

    x1 = max(0, min(int(round(x1)), src_w - 1))
    y1 = max(0, min(int(round(y1)), src_h - 1))
    x2 = max(0, min(int(round(x2)), src_w - 1))
    y2 = max(0, min(int(round(y2)), src_h - 1))

    return [x1, y1, x2, y2]


def map_detections_to_original(
    detections: list[dict],
    preprocess_meta: dict,
) -> list[dict]:
    mapped = []

    for det in detections:
        det2 = dict(det)
        det2["bbox"] = map_bbox_to_original(det["bbox"], preprocess_meta)
        mapped.append(det2)

    return mapped


class PreprocessStage:
    name = "preprocess_for_model"

    def __init__(
        self,
        mode: str = "direct_resize",
        model_width: int = 640,
        model_height: int = 640,
        crop_top_ratio: float = 0.0,
    ):
        self.mode = mode
        self.model_width = model_width
        self.model_height = model_height
        self.crop_top_ratio = crop_top_ratio

    def __call__(self, packet: FramePacket) -> FramePacket:
        frame = packet.frame
        src_h, src_w = frame.shape[:2]

        if self.mode == "direct_resize":
            model_input = cv2.resize(
                frame,
                (self.model_width, self.model_height),
                interpolation=cv2.INTER_AREA,
            )

            packet.model_input_frame = model_input
            packet.preprocess_meta = {
                "mode": "direct_resize",
                "src_width": src_w,
                "src_height": src_h,
                "roi_x": 0,
                "roi_y": 0,
                "roi_w": src_w,
                "roi_h": src_h,
                "dst_width": self.model_width,
                "dst_height": self.model_height,
                "scale_x": src_w / float(self.model_width),
                "scale_y": src_h / float(self.model_height),
            }
            return packet

        if self.mode == "bottom_crop_resize":
            top_cut = int(src_h * self.crop_top_ratio)
            top_cut = max(0, min(top_cut, src_h - 1))

            roi_x = 0
            roi_y = top_cut
            roi_w = src_w
            roi_h = src_h - top_cut

            roi = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]

            model_input = cv2.resize(
                roi,
                (self.model_width, self.model_height),
                interpolation=cv2.INTER_AREA,
            )

            packet.model_input_frame = model_input
            packet.preprocess_meta = {
                "mode": "bottom_crop_resize",
                "src_width": src_w,
                "src_height": src_h,
                "roi_x": roi_x,
                "roi_y": roi_y,
                "roi_w": roi_w,
                "roi_h": roi_h,
                "dst_width": self.model_width,
                "dst_height": self.model_height,
                "scale_x": roi_w / float(self.model_width),
                "scale_y": roi_h / float(self.model_height),
            }
            return packet

        raise ValueError(f"Unsupported preprocess mode: {self.mode}")


class YoloDetectionStage:
    name = "yolo_inference"

    def __init__(self, detector: YoloDetector, conf: float = 0.3):
        self.detector = detector
        self.conf = conf

    def __call__(self, packet: FramePacket) -> FramePacket:
        image = (
            packet.model_input_frame
            if packet.model_input_frame is not None
            else packet.frame
        )

        detections = self.detector.detect(
            image,
            confidence_threshold=self.conf,
        )

        if packet.preprocess_meta:
            detections = map_detections_to_original(
                detections,
                packet.preprocess_meta,
            )

        packet.detections = detections
        return packet


class DrawDetectionsStage:
    name = "draw_detections"

    def __init__(self, color=(0, 255, 0), thickness: int = 2):
        self.color = color
        self.thickness = thickness

    def __call__(self, packet: FramePacket) -> FramePacket:
        img = packet.frame.copy()

        for det in packet.detections:
            x1, y1, x2, y2 = map(int, det["bbox"])

            track_id = det.get("track_id")
            if track_id is not None:
                label = f'#{track_id} {det["class_name"]} {det["confidence"]:.2f}'
            else:
                label = f'{det["class_name"]} {det["confidence"]:.2f}'

            cv2.rectangle(img, (x1, y1), (x2, y2), self.color, self.thickness)
            cv2.putText(
                img,
                label,
                (x1, max(y1 - 5, 0)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                self.color,
                1,
                cv2.LINE_AA,
            )

        packet.annotated_frame = img
        return packet