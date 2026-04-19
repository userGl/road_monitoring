# core/runtime_state.py
from __future__ import annotations

from threading import RLock
from typing import Optional, Any

_lock = RLock()

enable_output_stream: bool = True
yolo_stage: Optional[Any] = None

mode: str = "rtsp"   # "rtsp" | "idle" | "test_images"
mode_lock = RLock()

# Параметры для test_images (будут задаваться через API)
test_input_dir: Optional[str] = None
test_output_dir: Optional[str] = None
test_fps: Optional[int] = None