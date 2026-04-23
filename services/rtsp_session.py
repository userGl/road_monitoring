# services/rtsp_session.py
from sensors.ffmpeg_camera import FFmpegRTSPCamera
from sensors.rtsp_streamer import create_rtsp_streamer

from pipeline.stages import YoloDetectionStage
from inference.yolo_detector import YoloDetector

from core.runtime_config import (
    get_nested,
    sync_runtime_targets,
    snapshot_applied_config,
    apply_runtime_changes,
)

from core import runtime_state

from services.pipeline_builder import build_pipeline, make_pipeline


def run_rtsp_session(
    *,
    cfg,
    input_rtsp_url: str,
    output_rtsp_url: str,
    use_hwaccel: bool,
    preview_width: int,
    preview_height: int,
    model_path: str,
    detector_conf: float,
) -> None:
    """
    Одна RTSP-сессия: подключается к входному RTSP-потоку,
    создаёт пайплайн обработки кадров и при необходимости публикует выходной RTSP-поток.

    Сессия завершается:
    - при ошибке камеры или стримера;
    - при смене режима работы (runtime_state.mode != "rtsp").
    """
    # Камера читает входной RTSP-поток через ffmpeg.
    camera = FFmpegRTSPCamera(input_rtsp_url, use_hwaccel=use_hwaccel)
    print("[main] RTSP input started, API on :8081")

    meta_printed = False
    streamer = None
    detector = YoloDetector(model_path=model_path)
    yolo_stage = YoloDetectionStage(detector=detector, conf=detector_conf)

    # На старте output stream может быть ещё не поднят,
    # поэтому пайплайн сначала собираем без DrawDetectionsStage.
    # Tracker stage при этом остаётся включённым.
    draw_enabled = False
    pipeline, tracker_stage = build_pipeline(
        preview_width=preview_width,
        preview_height=preview_height,
        yolo_stage=yolo_stage,
        draw_enabled=draw_enabled,
    )
    runtime_state.tracker_stage = tracker_stage

    last_draw_enabled = draw_enabled

    runtime_state.yolo_stage = yolo_stage

    # Сохраняем в runtime_state целевые значения конфигурации.
    # REST API меняет именно эти поля, а main-loop применяет их к живым объектам.
    enable_output_stream = get_nested(
        cfg, "stream", "enable_output_stream", default=True
    )
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

    def should_stop_rtsp() -> bool:
        with runtime_state.mode_lock:
            return getattr(runtime_state, "mode", "rtsp") != "rtsp"

    try:
        for packet in camera.frames(should_stop=should_stop_rtsp):
            # Выходим из RTSP-сессии при смене режима (по команде API).
            with runtime_state.mode_lock:
                if getattr(runtime_state, "mode", "rtsp") != "rtsp":
                    print(
                        f"[main] RTSP session stopped due to mode change: "
                        f"{runtime_state.mode}"
                    )
                    break

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
            # убираем его из main-loop. Пайплайн ниже будет пересобран без draw-stage,
            # но tracker stage останется включённым.
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
            # Tracker stage включён всегда.
            if draw_enabled != last_draw_enabled:
                pipeline = make_pipeline(
                    preview_width=preview_width,
                    preview_height=preview_height,
                    yolo_stage=yolo_stage,
                    tracker_stage=tracker_stage,
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