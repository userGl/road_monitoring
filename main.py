# main.py
"""
Поднимает REST API, запускает захват RTSP-источника, собирает пайплайн
обработки кадров и при необходимости публикует выходной RTSP-поток.
"""

import threading
import time

import uvicorn

from inference.yolo_detector import DEFAULT_MODEL_PATH

from core.runtime_config import (
    init_runtime_config,
    load_config,
    get_nested,
)
from core import runtime_state

from services.rtsp_session import run_rtsp_session
from services.images_batch import run_images_batch_session


def run_api():
    """Запускает REST API через uvicorn."""
    from api.rest_api import app

    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


def main():
    """Запускает основной видео-пайплайн приложения.

    Шаги:
    1. Загружает конфигурацию.
    2. Поднимает REST API в отдельном потоке.
    3. Подключается к входному RTSP-потоку.
    4. Создаёт пайплайн обработки кадров.
    5. При включённом output stream публикует обработанные кадры в RTSP.
    """
    cfg = load_config()

    input_rtsp_url = get_nested(
        cfg, "stream", "input_rtsp_url", default="rtsp://127.0.0.1:8554/live"
    )

    output_rtsp_url = get_nested(
        cfg, "stream", "output_rtsp_url", default="rtsp://127.0.0.1:8554/preview"
    )

    enable_output_stream = get_nested(
        cfg, "stream", "enable_output_stream", default=True
    )

    use_hwaccel = get_nested(cfg, "camera", "use_hwaccel", default=False)

    preview_width = int(get_nested(cfg, "preview", "width", default=640))
    preview_height = int(get_nested(cfg, "preview", "height", default=640))

    model_path = get_nested(cfg, "detector", "model_path", default=DEFAULT_MODEL_PATH)

    detector_conf = float(
        get_nested(cfg, "detector", "confidence_threshold", default=0.05)
    )

    # Инициализируем runtime-config с нужными полями
    init_runtime_config(
        {
            "stream": {
                "enable_output_stream": enable_output_stream,
            },
            "detector": {
                "confidence_threshold": detector_conf,
                "model_path": model_path,
            },
        }
    )

    # REST API работает параллельно с основным видеопотоком.
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    # Инициализируем режим работы по умолчанию.
    # Возможные значения: "rtsp", "idle", "test_images".
    if not hasattr(runtime_state, "mode"):
        runtime_state.mode = "rtsp"

    if not hasattr(runtime_state, "mode_lock"):
        from threading import RLock

        runtime_state.mode_lock = RLock()

    # Параметры для тестового режима будут задаваться через API.
    if not hasattr(runtime_state, "test_input_dir"):
        runtime_state.test_input_dir = None
    if not hasattr(runtime_state, "test_output_dir"):
        runtime_state.test_output_dir = None
    if not hasattr(runtime_state, "test_fps"):
        runtime_state.test_fps = None

    print("[main] Main control loop started")

    # Управляющий цикл: в зависимости от режима запускает RTSP-сессию
    # или однократную batch-сессию обработки изображений.
    while True:
        with runtime_state.mode_lock:
            mode = getattr(runtime_state, "mode", "rtsp")
            test_input_dir = getattr(runtime_state, "test_input_dir", None)
            test_output_dir = getattr(runtime_state, "test_output_dir", None)
            test_fps = getattr(runtime_state, "test_fps", None)

        if mode == "rtsp":
            # Подключается к входному RTSP-потоку.
            # Создаёт пайплайн обработки кадров.
            # При включённом output stream публикует обработанные кадры в RTSP.
            run_rtsp_session(
                cfg=cfg,
                input_rtsp_url=input_rtsp_url,
                output_rtsp_url=output_rtsp_url,
                use_hwaccel=use_hwaccel,
                preview_width=preview_width,
                preview_height=preview_height,
                model_path=model_path,
                detector_conf=detector_conf,
            )
            continue

        if mode == "test_images":
            if not test_input_dir or not test_output_dir:
                print(
                    "[main] test_images mode requested, "
                    "but test_input_dir/test_output_dir not set"
                )
                with runtime_state.mode_lock:
                    runtime_state.mode = "idle"
                continue

            run_images_batch_session(
                input_dir=test_input_dir,
                output_dir=test_output_dir,
                fps=test_fps or 5,
                cfg=cfg,
                model_path=model_path,
                detector_conf=detector_conf,
            )

            # После batch-сессии переходим в режим ожидания команды.
            with runtime_state.mode_lock:
                runtime_state.mode = "idle"

            continue

        if mode == "idle":
            # Если ничего не делать, ждём команды.
            time.sleep(0.5)
            continue


if __name__ == "__main__":
    main()