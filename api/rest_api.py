"""
Минимальный REST API endpoint для тестирования детекции
POST /api/v1/test/detect — тест детекции (POST base64 image)
"""
import base64
import logging
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(title="Road Damage Detection API")


class Base64ImageRequest(BaseModel):
    """Запрос с base64 изображением"""
    image: str  # base64 encoded image
    confidence_threshold: Optional[float] = 0.6


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


def mock_detection(image: np.ndarray, confidence_threshold: float) -> list:
    """
    Заглушка детекции для тестирования API
    Возвращает тестовые результаты детекции
    """
    h, w = image.shape[:2]
    
    # Тестовые детекции
    detections = [
        {
            'class_id': 3,
            'class_name': 'D40',
            'confidence': 0.85,
            'bbox': [w * 0.2, h * 0.3, w * 0.4, h * 0.5]
        },
        {
            'class_id': 0,
            'class_name': 'D00',
            'confidence': 0.72,
            'bbox': [w * 0.6, h * 0.4, w * 0.9, h * 0.45]
        }
    ]
    
    # Фильтруем по confidence
    return [d for d in detections if d['confidence'] >= confidence_threshold]


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
        
        # Выполнение детекции (заглушка)
        detections = mock_detection(image, request.confidence_threshold)
        
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
