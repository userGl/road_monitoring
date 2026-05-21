# services/pipeline_builder.py
from pipeline.core import VideoPipeline
from pipeline.stages import (
    PreprocessStage,
    YoloDetectionStage,
    DrawDetectionsStage,
    StageProfiler,
)
from tracking.rdd_tracker import RDDTracker
from tracking.tracker_stage import RDDTrackerStage


def make_pipeline(
    *,
    model_input_width: int,
    model_input_height: int,
    yolo_stage: YoloDetectionStage,
    tracker_stage,
    draw_enabled: bool,
    storage_stage=None,
    preprocess_mode: str = "direct_resize",
    crop_top_ratio: float = 0.0,
):
    profiler = StageProfiler(enabled=True)

    stages = [
        profiler.wrap(
            PreprocessStage(
                mode=preprocess_mode,
                model_width=model_input_width,
                model_height=model_input_height,
                crop_top_ratio=crop_top_ratio,
            )
        ),
        profiler.wrap(yolo_stage),
        profiler.wrap(tracker_stage),
    ]

    if storage_stage is not None:
        stages.append(profiler.wrap(storage_stage))

    if draw_enabled:
        stages.append(profiler.wrap(DrawDetectionsStage()))

    pipeline = VideoPipeline(stages=stages)
    pipeline.profiler = profiler
    return pipeline

def build_pipeline(
    model_input_width: int,
    model_input_height: int,
    yolo_stage: YoloDetectionStage,
    draw_enabled: bool,
    storage_stage=None,
    preprocess_mode: str = "direct_resize",
    crop_top_ratio: float = 0.0,
) -> tuple[VideoPipeline, RDDTrackerStage]:
    """Собирает пайплайн обработки кадров.

    Базовый пайплайн: предобработка -> детекция -> трекинг.
    При включённой отрисовке добавляется DrawDetectionsStage.
    """
    tracker_stage = RDDTrackerStage(RDDTracker())

    pipeline = make_pipeline(
        model_input_width=model_input_width,
        model_input_height=model_input_height,
        yolo_stage=yolo_stage,
        tracker_stage=tracker_stage,
        draw_enabled=draw_enabled,
        storage_stage=storage_stage,
        preprocess_mode=preprocess_mode,
        crop_top_ratio=crop_top_ratio,
    )
    return pipeline, tracker_stage