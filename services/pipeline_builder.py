from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage, YoloDetectionStage, DrawDetectionsStage
from tracking.rdd_tracker import RDDTracker
from tracking.tracker_stage import RDDTrackerStage


def build_pipeline(
    preview_width: int,
    preview_height: int,
    yolo_stage: YoloDetectionStage,
    draw_enabled: bool,
) -> VideoPipeline:
    """Собирает пайплайн обработки кадров.

    Базовый пайплайн: ресайз -> детекция -> трекинг.
    При включённой отрисовке добавляется DrawDetectionsStage.
    """
    tracker_stage = RDDTrackerStage(RDDTracker())

    stages = [
        ResizeStage(width=preview_width, height=preview_height),
        yolo_stage,
        tracker_stage,
    ]

    if draw_enabled:
        stages.append(DrawDetectionsStage())

    return VideoPipeline(stages=stages)