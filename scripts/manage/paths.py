import os
import platform
from pathlib import Path

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8081/api/v1")
CONFIG_URL = f"{BASE_URL}/config"
CONTROL_URL = f"{BASE_URL}/control"
TEST_IMAGES_URL = f"{BASE_URL}/test/images"

SCRIPT_DIR = Path(__file__).resolve().parent.parent
APP_DIR = SCRIPT_DIR.parent
APP_ENTRY = APP_DIR / "main.py"
MODELS_DIR = APP_DIR / "models"
TEST_IMAGES_ROOT = APP_DIR / "test_images"
RUN_DIR = APP_DIR / ".run"
MAIN_APP_PID_FILE = RUN_DIR / "main_app.pid"
RTSP_PUBLISHER_PID_FILE = RUN_DIR / "rtsp_publisher.pid"

IS_WINDOWS = platform.system() == "Windows"
START_RTSP_SCRIPT = SCRIPT_DIR / ("start_mediamtx_rtsp.ps1" if IS_WINDOWS else "start_mediamtx_rtsp.sh")
VIEW_RTSP_SCRIPT = SCRIPT_DIR / ("rtsp_view.ps1" if IS_WINDOWS else "rtsp_view.sh")
