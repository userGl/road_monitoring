from pipeline.core import VideoPipeline
from pipeline.stages import ResizeStage, YoloDetectionStage, DrawDetectionsStage


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