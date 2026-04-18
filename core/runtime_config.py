from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from core import runtime_state
from inference.yolo_detector import YoloDetector
from pipeline.stages import YoloDetectionStage


_lock = RLock()

_runtime_config: dict[str, Any] = {
    "stream": {
        "enable_output_stream": True,
    },
    "detector": {
        "confidence_threshold": 0.05,
        "model_path": "models/epoch40.pt",
    },
}


def init_runtime_config(initial_config: dict[str, Any]) -> None:
    """Инициализирует runtime-config начальными значениями."""
    with _lock:
        _merge_dict(_runtime_config, initial_config)


def get_runtime_config() -> dict[str, Any]:
    """Возвращает копию текущего runtime-config."""
    with _lock:
        return deepcopy(_runtime_config)


def patch_runtime_config(patch: dict[str, Any]) -> dict[str, Any]:
    """Частично обновляет runtime-config и возвращает его копию."""
    with _lock:
        _merge_dict(_runtime_config, patch)
        return deepcopy(_runtime_config)


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Загружает конфигурацию из YAML-файла."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    else:
        config_path = Path(config_path)

    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_nested(d: dict[str, Any], *keys, default=None):
    """Безопасно читает вложенное значение из словаря."""
    cur = d
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def sync_runtime_targets(
    *,
    enable_output_stream: bool,
    confidence_threshold: float,
    model_path: str,
) -> None:
    """Инициализирует целевое runtime-состояние, которое main-loop будет применять."""
    runtime_state.enable_output_stream = enable_output_stream
    runtime_state.confidence_threshold = confidence_threshold
    runtime_state.model_path = model_path


def snapshot_applied_config(
    *,
    enable_output_stream: bool,
    confidence_threshold: float,
    model_path: str,
) -> dict[str, Any]:
    """Возвращает слепок уже применённых к живым объектам параметров."""
    return {
        "stream": {
            "enable_output_stream": enable_output_stream,
        },
        "detector": {
            "confidence_threshold": confidence_threshold,
            "model_path": model_path,
        },
    }


def apply_runtime_changes(
    *,
    last_applied_cfg: dict[str, Any],
    yolo_stage: YoloDetectionStage,
) -> dict[str, Any]:
    """Применяет runtime-изменения без полного рестарта процесса."""
    applied = {
        "stream": {
            "enable_output_stream": last_applied_cfg["stream"]["enable_output_stream"],
        },
        "detector": {
            "confidence_threshold": last_applied_cfg["detector"]["confidence_threshold"],
            "model_path": last_applied_cfg["detector"]["model_path"],
        },
    }

    target_enable_output_stream = getattr(
        runtime_state,
        "enable_output_stream",
        last_applied_cfg["stream"]["enable_output_stream"],
    )
    target_confidence = float(
        getattr(
            runtime_state,
            "confidence_threshold",
            last_applied_cfg["detector"]["confidence_threshold"],
        )
    )
    target_model_path = getattr(
        runtime_state,
        "model_path",
        last_applied_cfg["detector"]["model_path"],
    )

    old_confidence = last_applied_cfg["detector"]["confidence_threshold"]
    if target_confidence != old_confidence:
        yolo_stage.conf = target_confidence
        applied["detector"]["confidence_threshold"] = target_confidence
        print(f"[main] confidence_threshold updated: {old_confidence} -> {target_confidence}")

    old_model_path = last_applied_cfg["detector"]["model_path"]
    if target_model_path != old_model_path:
        print(f"[main] Reloading detector model: {old_model_path} -> {target_model_path}")
        try:
            new_detector = YoloDetector(model_path=target_model_path)
        except Exception as e:
            print(f"[main] Failed to reload detector model '{target_model_path}': {e}")
            runtime_state.model_path = old_model_path
            applied["detector"]["model_path"] = old_model_path
        else:
            yolo_stage.detector = new_detector
            applied["detector"]["model_path"] = target_model_path
            print(f"[main] Detector model reloaded: {target_model_path}")

    applied["stream"]["enable_output_stream"] = target_enable_output_stream
    return applied


def _merge_dict(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge_dict(dst[key], value)
        else:
            dst[key] = value