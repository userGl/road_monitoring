"""
Минимальный REST API endpoint для тестирования детекции
POST /api/v1/test/detect — тест детекции (POST base64 image)
"""
import base64
import logging
import os
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ultralytics import YOLO

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(title="Road Damage Detection API")

# Загрузка модели YOLOv8 при старте приложения
# MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
MODEL_PATH = os.getenv("MODEL_PATH", "models/epoch50.pt")
# MODEL_PATH = os.getenv("MODEL_PATH", "models/YOLOv8_Small_v1.pt")
# MODEL_PATH = os.getenv("MODEL_PATH", "models/yolov8s.pt")
model = None
device = None

def get_device():
    """Определение устройства для инференса (GPU или CPU)"""
    if torch.cuda.is_available():
        device_id = 0
        device_name = torch.cuda.get_device_name(0)
        logger.info(f"CUDA доступна. Используется GPU: {device_name}")
        return device_id
    else:
        logger.warning("CUDA недоступна. Используется CPU (инференс будет медленнее)")
        return "cpu"

def load_model():
    """Загрузка модели YOLO"""
    global model, device
    try:
        if os.path.exists(MODEL_PATH):
            logger.info(f"Загрузка модели: {MODEL_PATH}")
            device = get_device()
            model = YOLO(MODEL_PATH)
            logger.info(f"Модель успешно загружена. Устройство для инференса: {device}")
        else:
            logger.warning(f"Модель не найдена: {MODEL_PATH}. Пожалуйста, проверьте путь к модели."
            )
            model = None
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}")
        model = None

# Загружаем модель при импорте модуля
load_model()


class Base64ImageRequest(BaseModel):
    """Запрос с base64 изображением"""
    image: str  # base64 encoded image
    confidence_threshold: Optional[float] = 0.3


class DetectionResult(BaseModel):
    """Результат детекции"""
    class_id: int
    class_name: str
    confidence: float
    bbox: list  # [x_min, y_min, x_max, y_max]


class DetectionResponse(BaseModel):
    """Ответ на запрос детекции"""
    success: bool
    timestamp: str
    image_shape: list  # [height, width, channels]
    detections: list[DetectionResult]
    processing_time_ms: float
    message: Optional[str] = None


def decode_base64_image(base64_string: str) -> np.ndarray:
    """Декодирование base64 в изображение OpenCV"""
    try:
        # Удаляем префикс data:image/...;base64, если есть
        if ',' in base64_string:
            base64_string = base64_string.split(',')[1]
        
        # Декодируем base64
        image_bytes = base64.b64decode(base64_string)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Не удалось декодировать изображение")
        
        return image
    except Exception as e:
        logger.error(f"Ошибка декодирования: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка декодирования изображения: {str(e)}")


def run_yolo_detection(image: np.ndarray, confidence_threshold: float) -> list:
    """
    Выполнение детекции с помощью YOLO
    Возвращает результаты детекции в формате API
    """
    global model
    
    if model is None:
        logger.error(f"Модель не загружена: {MODEL_PATH}")
        raise HTTPException(
            status_code=503, 
            detail=f"Модель не найдена: {MODEL_PATH}. Пожалуйста, проверьте путь к модели."
        )
    
    try:
        # Запускаем детекцию с явным указанием устройства
        global device
        if device is None:
            device = get_device()
        results = model(image, conf=confidence_threshold, device=device, verbose=False)
        
        detections = []
        if len(results) > 0 and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = box.xyxy[0].cpu().numpy()
                class_name = model.names[cls]
                
                detections.append({
                    'class_id': cls,
                    'class_name': class_name,
                    'confidence': conf,
                    'bbox': [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
                })
        
        return detections
    except Exception as e:
        logger.error(f"Ошибка при детекции YOLOv8: {e}", exc_info=True)
        raise


@app.post("/api/v1/test/detect", response_model=DetectionResponse)
async def test_detect(request: Base64ImageRequest):
    """
    Тест детекции дефектов дорожного полотна
    Принимает base64 закодированное изображение
    """
    start_time = datetime.now()
    
    try:
        # Декодирование изображения
        image = decode_base64_image(request.image)
        image_shape = list(image.shape)
        
        # Выполнение детекции с помощью YOLOv8
        detections = run_yolo_detection(image, request.confidence_threshold)
        
        # Время обработки
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Формирование ответа
        detection_results = [
            DetectionResult(**det) for det in detections
        ]
        
        return DetectionResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            image_shape=image_shape,
            detections=detection_results,
            processing_time_ms=round(processing_time, 2),
            message=f"Обнаружено дефектов: {len(detection_results)}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при детекции: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")
