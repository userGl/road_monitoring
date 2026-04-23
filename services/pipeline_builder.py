# services/pipeline_builder.py  
from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage, YoloDetectionStage, DrawDetectionsStage
from tracking.rdd_tracker import RDDTracker
from tracking.tracker_stage import RDDTrackerStage


def make_pipeline(
    preview_width: int,
    preview_height: int,
    yolo_stage: YoloDetectionStage,
    tracker_stage: RDDTrackerStage,
    draw_enabled: bool,
) -> VideoPipeline:
    """Собирает пайплайн обработки кадров с уже существующим tracker stage."""

    stages = [
        ResizeStage(width=preview_width, height=preview_height),
        yolo_stage,
        tracker_stage,
    ]

    if draw_enabled:
        stages.append(DrawDetectionsStage())

    return VideoPipeline(stages=stages)


def build_pipeline(
    preview_width: int,
    preview_height: int,
    yolo_stage: YoloDetectionStage,
    draw_enabled: bool,
) -> tuple[VideoPipeline, RDDTrackerStage]:
    """Собирает пайплайн обработки кадров.

    Базовый пайплайн: ресайз -> детекция -> трекинг.
    При включённой отрисовке добавляется DrawDetectionsStage.
    """
    tracker_stage = RDDTrackerStage(RDDTracker())

    pipeline = make_pipeline(
        preview_width=preview_width,
        preview_height=preview_height,
        yolo_stage=yolo_stage,
        tracker_stage=tracker_stage,
        draw_enabled=draw_enabled,
    )

    return pipeline, tracker_stage