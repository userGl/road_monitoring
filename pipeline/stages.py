# pipeline/stages.py
from typing import Protocol
import cv2


class Stage(Protocol):
    name: str

    def __call__(self, packet):
        ...


class ResizeStage:
    name = "resize_for_model"

    def __init__(self, width: int = 640, height: int = 640):
        self.width = width
        self.height = height

    def __call__(self, packet):
        packet.resized_frame = cv2.resize(
            packet.frame,
            (self.width, self.height),
            interpolation=cv2.INTER_AREA
        )
        return packet