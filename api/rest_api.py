# api/rest_api.py
"""
REST API приложения.

Поддерживает:
- GET /api/v1/config
- PATCH /api/v1/config
- POST /api/v1/test/detect
"""
import base64
import logging
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.runtime_config import get_runtime_config, patch_runtime_config
from core import runtime_state

# Настройка логирования
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(title="Road Damage Detection API")

# Pydantic-модели для конфигурации
class StreamConfigResponse(BaseModel):
    enable_output_stream: bool

class DetectorConfigResponse(BaseModel):
    confidence_threshold: float
    model_path: str

class AppConfigResponse(BaseModel):
    stream: StreamConfigResponse
    detector: DetectorConfigResponse

class StreamConfigPatch(BaseModel):
    enable_output_stream: Optional[bool] = None

class DetectorConfigPatch(BaseModel):
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    model_path: Optional[str] = None

class AppConfigPatch(BaseModel):
    stream: Optional[StreamConfigPatch] = None
    detector: Optional[DetectorConfigPatch] = None

class ConfigPatchResponse(BaseModel):
    success: bool
    config: AppConfigResponse
    applied: dict[str, str]


class Base64ImageRequest(BaseModel):
    """Запрос с base64 изображением"""
    image: str  # base64 encoded image
    confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)


class DetectionResult(BaseModel):
    """Результат детекции"""
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x_min, y_min, x_max, y_max] 


class DetectionResponse(BaseModel):
    """Ответ на запрос детекции"""
    success: bool
    timestamp: str
    image_shape: list[int]  # [height, width, channels]
    detections: list[DetectionResult]
    processing_time_ms: float
    message: Optional[str] = None


def decode_base64_image(base64_string: str) -> np.ndarray:
    """Декодирование base64 в изображение OpenCV"""
    try:
        # Удаляем префикс data:image/...;base64, если есть
        if ',' in base64_string:
            base64_string = base64_string.split(',', 1)[1]
        
        # Декодируем base64
        image_bytes = base64.b64decode(base64_string)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise ValueError("Не удалось декодировать изображение")
        
        return image
    except Exception as e:
        logger.exception("Ошибка декодирования изображения")
        raise HTTPException(status_code=400, detail=f"Ошибка декодирования изображения: {str(e)}")


# Endpoint для получения текущей конфигурации
@app.get("/api/v1/config", response_model=AppConfigResponse)
async def get_config():
    """Возвращает текущую активную конфигурацию."""
    cfg = get_runtime_config()
    return AppConfigResponse(**cfg)

# Endpoint для частичного обновления конфигурации
@app.patch("/api/v1/config", response_model=ConfigPatchResponse)
async def patch_config(body: AppConfigPatch):
    """Частично обновляет конфигурацию приложения."""
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Пустой PATCH-запрос")

    applied: dict[str, str] = {}

    # 1. Сначала обновляем runtime-config как источник истины для API и UI.
    # Применение изменений к живым объектам выполняется в main-loop.
    cfg = patch_runtime_config(patch)

    # 2. Обновляем целевое runtime-состояние.
    # Main-loop увидит изменение и сам поднимет/остановит RTSP output.
    if body.stream and body.stream.enable_output_stream is not None:
        runtime_state.enable_output_stream = body.stream.enable_output_stream
        applied["stream.enable_output_stream"] = "updated"

    # 3. Обновляем целевое значение confidence.
    # Main-loop применит его к YoloDetectionStage без рестарта процесса.
    if body.detector and body.detector.confidence_threshold is not None:
        runtime_state.confidence_threshold = body.detector.confidence_threshold
        applied["detector.confidence_threshold"] = "updated"

    # 4. Обновляем целевое значение model_path.
    # Main-loop применит его к YoloDetector через создание нового объекта.
    if body.detector and body.detector.model_path is not None:
        runtime_state.model_path = body.detector.model_path
        applied["detector.model_path"] = "updated"
    
    return ConfigPatchResponse(
        success=True,
        config=AppConfigResponse(**cfg),
        applied=applied,
    )

# Endpoint для тестирования детекции
@app.post("/api/v1/test/detect", response_model=DetectionResponse)
async def test_detect(request: Base64ImageRequest):
    """
    Тест детекции дефектов дорожного полотна.
    Принимает base64-кодированное изображение.
    """
    start_time = datetime.now()

    try:
        image = decode_base64_image(request.image)
        image_shape = list(image.shape)

        stage = runtime_state.yolo_stage
        if stage is None:
            raise HTTPException(
                status_code=503,
                detail="YoloDetectionStage недоступен.",
            )

        detector = stage.detector
        if not detector.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Модель не загружена.",
            )

        detections = detector.detect(
            image,
            confidence_threshold=request.confidence_threshold,
        )

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        detection_results = [DetectionResult(**det) for det in detections]

        return DetectionResponse(
            success=True,
            timestamp=datetime.now().isoformat(),
            image_shape=image_shape,
            detections=detection_results,
            processing_time_ms=round(processing_time, 2),
            message=f"Обнаружено дефектов: {len(detection_results)}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка при детекции")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")