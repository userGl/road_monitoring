# pipeline/stages.py
from typing import Protocol
import cv2

from core.frame_packet import FramePacket
from inference.yolo_detector import YoloDetector


class Stage(Protocol):
    name: str

    def __call__(self, packet: FramePacket) -> FramePacket:
        ...


class ResizeStage:
    name = "resize_for_model"

    def __init__(self, width: int = 640, height: int = 640):
        self.width = width
        self.height = height

    def __call__(self, packet: FramePacket) -> FramePacket:
        packet.resized_frame = cv2.resize(
            packet.frame,
            (self.width, self.height),
            interpolation=cv2.INTER_AREA,
        )
        return packet


class YoloDetectionStage:
    name = "yolo_inference"

    def __init__(self, detector: YoloDetector, conf: float = 0.3):
        self.detector = detector
        self.conf = conf

    def __call__(self, packet: FramePacket) -> FramePacket:
        image = packet.resized_frame if packet.resized_frame is not None else packet.frame
        packet.detections = self.detector.detect(
            image,
            confidence_threshold=self.conf,
        )
        return packet


class DrawDetectionsStage:
    name = "draw_detections"

    def __init__(self, color=(0, 255, 0), thickness: int = 2):
        self.color = color
        self.thickness = thickness

    def __call__(self, packet: FramePacket) -> FramePacket:
        img = (packet.resized_frame if packet.resized_frame is not None else packet.frame).copy()

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