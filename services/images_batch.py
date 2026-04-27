# services/images_batch.py
from pathlib import Path
import json
from typing import Any, Dict, List

import cv2

from sensors.image_folder_camera import ImageFolderCamera

from pipeline.stages import YoloDetectionStage
from inference.yolo_detector import YoloDetector

from core.runtime_config import (
    get_nested,
    sync_runtime_targets,
    snapshot_applied_config,
    apply_runtime_changes,
)

from core import runtime_state

from services.pipeline_builder import build_pipeline


def run_images_batch_session(
    *,
    input_dir: str,
    output_dir: str,
    fps: int,
    cfg,
    model_path: str,
    detector_conf: float,
) -> None:
    """
    Тестовый режим: однократная обработка папки с изображениями через пайплайн.

    Здесь:
    - создаётся пайплайн (Resize -> Yolo -> Tracker -> Draw);
    - источник кадров — ImageFolderCamera;
    - кадры прогоняются через pipeline;
    - аннотированные кадры и JSON сохраняются в output_dir.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(
        f"[main] Images batch session started: "
        f"input_dir='{input_path}', output_dir='{output_path}', fps={fps}"
    )

    # Источник кадров из папки, имитирующий видеопоток.
    try:
        camera = ImageFolderCamera(str(input_path), fps=fps)
    except Exception as e:
        print(f"[main] Images batch session: failed to init ImageFolderCamera: {e}")
        return

    # Создаём детектор и стадию YOLO для batch-режима.
    detector = YoloDetector(model_path=model_path)
    yolo_stage = YoloDetectionStage(detector=detector, conf=detector_conf)
    runtime_state.yolo_stage = yolo_stage

    # Используем размеры предпросмотра из общего конфига.
    model_input_width = int(get_nested(cfg, "model_input", "width", default=640))
    model_input_height = int(get_nested(cfg, "model_input", "height", default=640))

    # В тестовом режиме отрисовка всегда включена, чтобы сразу видеть результат.
    draw_enabled = True
    pipeline, tracker_stage = build_pipeline(
        model_input_width=model_input_width,
        model_input_height=model_input_height,
        yolo_stage=yolo_stage,
        draw_enabled=draw_enabled,
    )
    runtime_state.tracker_stage = tracker_stage

    # Инициализация runtime-targets и слепка применённой конфигурации.
    enable_output_stream = get_nested(
        cfg, "stream", "enable_output_stream", default=True
    )

    sync_runtime_targets(
        enable_output_stream=enable_output_stream,
        confidence_threshold=detector_conf,
        model_path=model_path,
    )

    last_applied_cfg: Dict[str, Any] = snapshot_applied_config(
        enable_output_stream=enable_output_stream,
        confidence_threshold=detector_conf,
        model_path=model_path,
    )

    results: List[Dict[str, Any]] = []
    processed_frames = 0

    # Фиксируем стартовые значения модели и порога.
    initial_model_path = model_path
    initial_confidence_threshold = detector_conf

    try:
        for packet in camera.frames():
            # На каждом "кадре" сначала применяем накопившиеся runtime-изменения,
            # и только потом работаем с пайплайном.
            last_applied_cfg = apply_runtime_changes(
                last_applied_cfg=last_applied_cfg,
                yolo_stage=yolo_stage,
            )

            # Прогоняем кадр через все стадии пайплайна.
            packet = pipeline.process(packet)


            # Приоритет сохранения:
            # 1. annotated_frame — если кадр уже размечен;
            # 2. frame — исходный кадр как fallback.
            frame_to_save = (
                packet.annotated_frame
                if packet.annotated_frame is not None
                else packet.frame
            )
            # Имя выходного файла такое же, как у входного.
            input_path_str = packet.meta.get("input_path")
            if input_path_str:
                in_name = Path(input_path_str).name
            else:
                in_name = f"frame_{packet.frame_id:06d}.jpg"

            out_img_path = output_path / in_name
            if frame_to_save is not None:
                cv2.imwrite(str(out_img_path), frame_to_save)
            else:
                print(
                    f"[main] Images batch session: nothing to save for frame_id={packet.frame_id} "
                    "(no frame in packet)"
                )

            detections_json: List[Dict[str, Any]] = []
            for det in packet.detections:
                detections_json.append(
                    {
                        "bbox": det.get("bbox"),
                        "confidence": float(det.get("confidence", 0.0)),
                        "track_score": float(det.get("track_score", 0.0)),
                        "class_id": int(det.get("class_id", -1)),
                        "class_name": det.get("class_name"),
                        "track_id": det.get("track_id"),
                        "is_new": bool(det.get("is_new", False)),
                        "is_lost": bool(det.get("is_lost", False)),
                        "track_confirmed": bool(det.get("track_confirmed", False)),
                    }
                )

            tracks_json: List[Dict[str, Any]] = []
            for tr in getattr(packet, "tracks", []):
                tracks_json.append(
                    {
                        "track_id": int(tr.get("track_id", -1)),
                        "bbox": tr.get("bbox"),
                        "pred_bbox": tr.get("pred_bbox"),
                        "confidence": float(tr.get("confidence", 0.0)),
                        "best_confidence": float(tr.get("best_confidence", 0.0)),
                        "class_id": int(tr.get("class_id", -1)),
                        "class_name": tr.get("class_name"),
                        "confirmed": bool(tr.get("confirmed", False)),
                        "hit_count": int(tr.get("hit_count", 0)),
                        "miss_count": int(tr.get("miss_count", 0)),
                        "age": int(tr.get("age", 0)),
                    }
                )

            results.append(
                {
                    "frame_id": packet.frame_id,
                    "input": input_path_str,
                    "output": str(out_img_path),
                    "ts_monotonic": packet.ts_monotonic,
                    "ts_wall": packet.ts_wall,
                    "fps": packet.meta.get("fps"),
                    "detections": detections_json,
                    "tracks": tracks_json,
                }
            )

            processed_frames += 1

    finally:
        camera.release()

    # Фиксируем финальные значения модели и порога с учётом runtime-изменений.
    final_model_path = getattr(runtime_state, "model_path", initial_model_path)
    final_confidence_threshold = getattr(
        getattr(runtime_state, "yolo_stage", None),
        "conf",
        initial_confidence_threshold,
    )

    json_path = output_path / "detections_tracks.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "initial_model_path": initial_model_path,
                    "initial_confidence_threshold": float(
                        initial_confidence_threshold
                    ),
                    "final_model_path": final_model_path,
                    "final_confidence_threshold": float(
                        final_confidence_threshold
                    ),
                    "frames_processed": processed_frames,
                },
                "frames": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"[main] Images batch session finished: {processed_frames} frames processed, "
        f"JSON saved to '{json_path}'"
    )