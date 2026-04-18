# core/runtime_state.py
from __future__ import annotations

from threading import RLock
from typing import Optional, Any

_lock = RLock()

enable_output_stream: bool = True
yolo_stage: Optional[Any] = None