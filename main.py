# main.py
"""
Поднимает REST API, запускает захват RTSP-источника, собирает пайплайн
обработки кадров и при необходимости публикует выходной RTSP-поток.
"""

import threading

import uvicorn

from sensors.ffmpeg_camera import FFmpegRTSPCamera
from sensors.rtsp_streamer import create_rtsp_streamer

from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage, YoloDetectionStage, DrawDetectionsStage
from inference.yolo_detector import YoloDetector, DEFAULT_MODEL_PATH

from core.runtime_config import (
    init_runtime_config,
    load_config,
    get_nested,
    sync_runtime_targets,
    snapshot_applied_config,
    apply_runtime_changes,
)
from core import runtime_state


def run_api():
    """Запускает REST API через uvicorn."""
    from api.rest_api import app
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


def build_pipeline(
    preview_width: int,
    preview_height: int,
    yolo_stage: YoloDetectionStage,
    draw_enabled: bool,
) -> VideoPipeline:
    """Собирает пайплайн обработки кадров.

    Базовый пайплайн: ресайз -> детекция.
    При включённом output stream добавляется отрисовка результатов.
    """
    stages = [
        ResizeStage(width=preview_width, height=preview_height),
        yolo_stage,
    ]

    if draw_enabled:
        stages.append(DrawDetectionsStage())

    return VideoPipeline(stages=stages)


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

    # Камера читает входной RTSP-поток через ffmpeg.
    camera = FFmpegRTSPCamera(input_rtsp_url, use_hwaccel=use_hwaccel)
    print("[main] RTSP input started, API on :8081")

    meta_printed = False
    streamer = None
    detector = YoloDetector(model_path=model_path)
    yolo_stage = YoloDetectionStage(detector=detector, conf=detector_conf)

    # На старте output stream может быть ещё не поднят,
    # поэтому пайплайн собираем без DrawDetectionsStage.
    draw_enabled = False
    pipeline = build_pipeline(
        preview_width=preview_width,
        preview_height=preview_height,
        yolo_stage=yolo_stage,
        draw_enabled=draw_enabled,
    )
    last_draw_enabled = draw_enabled

    runtime_state.yolo_stage = yolo_stage

    # Сохраняем в runtime_state целевые значения конфигурации.
    # REST API меняет именно эти поля, а main-loop применяет их к живым объектам.
    sync_runtime_targets(
        enable_output_stream=enable_output_stream,
        confidence_threshold=detector_conf,
        model_path=model_path,
    )

    # Храним отдельный слепок уже ПРИМЕНЁННОЙ конфигурации.
    # Он нужен, чтобы main-loop мог понять, что именно изменилось с прошлого кадра.
    last_applied_cfg = snapshot_applied_config(
        enable_output_stream=enable_output_stream,
        confidence_threshold=detector_conf,
        model_path=model_path,
    )

    try:
        for packet in camera.frames():
            # Печатаем метаданные входного видеопотока один раз,
            # когда ffprobe/ffmpeg уже успешно открыли поток.
            if not meta_printed and camera.meta is not None:
                print(f"[main] Video meta: {camera.meta}")
                meta_printed = True

            # На каждом кадре сначала применяем накопившиеся runtime-изменения,
            # и только потом работаем со streamer и пайплайном.
            last_applied_cfg = apply_runtime_changes(
                last_applied_cfg=last_applied_cfg,
                yolo_stage=yolo_stage,
            )

            # Если RTSP streamer был аварийно отключён после серии рестартов,
            # убираем его из main-loop. Пайплайн ниже будет пересобран без draw-stage.
            if streamer is not None and streamer.is_disabled():
                streamer.stop()
                streamer = None
                print("[main] RTSP streamer disabled after failures")

            # Если output stream выключили через runtime-config,
            # останавливаем стример.
            if not runtime_state.enable_output_stream and streamer is not None:
                streamer.stop()
                streamer = None
                print("[main] RTSP output stopped")

            # Лениво поднимаем выходной RTSP-стример только после того,
            # как стали известны параметры входного потока.
            if (
                runtime_state.enable_output_stream
                and streamer is None
                and camera.meta is not None
            ):
                fps = int(camera.meta.fps) if camera.meta.fps else 25
                streamer = create_rtsp_streamer(
                    output_rtsp_url,
                    width=preview_width,
                    height=preview_height,
                    fps=fps,
                )
                print(
                    f"[main] RTSP output started: {output_rtsp_url} "
                    f"({preview_width}x{preview_height} @ {fps} fps)"
                )

            # Отрисовка нужна только тогда, когда реально активен output stream.
            draw_enabled = (
                runtime_state.enable_output_stream
                and streamer is not None
                and not streamer.is_disabled()
            )

            # Если режим output stream изменился, пересобираем пайплайн:
            # без draw-stage, когда стрим выключен, и с draw-stage, когда включён.
            if draw_enabled != last_draw_enabled:
                pipeline = build_pipeline(
                    preview_width=preview_width,
                    preview_height=preview_height,
                    yolo_stage=yolo_stage,
                    draw_enabled=draw_enabled,
                )
                last_draw_enabled = draw_enabled
                print(f"[main] Pipeline rebuilt: draw_enabled={draw_enabled}")

            # Прогоняем кадр через все стадии пайплайна.
            packet = pipeline.process(packet)

            # Приоритет отправки:
            # 1. annotated_frame — если кадр уже размечен;
            # 2. resized_frame — если есть только ресайз;
            # 3. frame — исходный кадр как fallback.
            frame_to_send = (
                packet.annotated_frame
                if packet.annotated_frame is not None
                else packet.resized_frame
                if packet.resized_frame is not None
                else packet.frame
            )

            if streamer is not None and not streamer.is_disabled():
                streamer.write(frame_to_send)

    finally:
        # Корректно освобождаем ресурсы при завершении приложения.
        if streamer is not None:
            streamer.stop()
        camera.release()


if __name__ == "__main__":
    main()
