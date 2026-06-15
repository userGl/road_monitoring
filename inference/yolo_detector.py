# inference/yolo_detector.py
import logging
import os
from typing import Any

import numpy as np
import torch
from ultralytics import YOLO

logger = logging.getLogger(__name__)

# Значение по умолчанию, если путь не задан в конфиге
DEFAULT_MODEL_PATH = os.getenv("MODEL_PATH", "models/epoch40.pt")

class YoloDetector:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.device: str | int = self._get_device()
        self.model: YOLO | None = None
        self._load_model()

    def _get_device(self) -> str | int:
        """Определение устройства для инференса (GPU или CPU)"""
        if torch.cuda.is_available():
            device_id = 0
            device_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA доступна. Используется GPU: {device_name}")
            return device_id
        logger.warning("CUDA недоступна. Используется CPU (инференс будет медленнее)")
        return "cpu"

    def _load_model(self) -> None:
        """Загрузка модели YOLO"""
        if not os.path.exists(self.model_path):
            logger.error(f"Модель не найдена: {self.model_path}")
            self.model = None
            return
        logger.info(f"Загрузка модели: {self.model_path}")
        self.model = YOLO(self.model_path)
        self.model.to(self.device)
        logger.info(f"Модель успешно загружена. Устройство: {self.device}")

    def is_ready(self) -> bool:
        return self.model is not None

    def detect(
    self,
    image_bgr: np.ndarray,
    confidence_threshold: float = 0.3,
) -> list[dict[str, Any]]:
        """Выполняет детекцию объектов на одном BGR-изображении.

        Подаёт входной кадр в модель YOLO и возвращает список детекций
        в формате, удобном для REST API и дальнейшей обработки.

        Args:
            image_bgr: Входное изображение в формате OpenCV/Numpy (BGR).
            confidence_threshold: Минимальный порог confidence для фильтрации
                предсказаний модели.

        Returns:
            Список детекций. Каждый элемент — словарь вида:
            {
                "class_id": int,
                "class_name": str,
                "confidence": float,
                "bbox": [x_min, y_min, x_max, y_max],
            }

            Если объектов не найдено, возвращается пустой список.

        Raises:
            RuntimeError: Если модель не была загружена.
        """
        if self.model is None:
            raise RuntimeError(f"Модель не загружена: {self.model_path}")

        results = self.model(
            image_bgr,
            conf=confidence_threshold,
            verbose=False,
        )

        detections: list[dict[str, Any]] = []
        if len(results) > 0 and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = box.xyxy[0].cpu().numpy()
                class_name = self.model.names[cls]

                detections.append(
                    {
                        "class_id": cls,
                        "class_name": class_name,
                        "confidence": conf,
                        "bbox": [
                            float(bbox[0]),
                            float(bbox[1]),
                            float(bbox[2]),
                            float(bbox[3]),
                        ],
                    }
                )
        return detections
