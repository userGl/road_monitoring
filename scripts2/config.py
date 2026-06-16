from pathlib import Path
import os
import platform

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8081/api/v1")
CONFIG_URL = f"{BASE_URL}/config"
CONTROL_URL = f"{BASE_URL}/control"
TEST_IMAGES_URL = f"{BASE_URL}/test/images"

PACKAGE_DIR = Path(__file__).resolve().parent
APP_DIR = PACKAGE_DIR.parent
SCRIPTS_DIR = APP_DIR / "scripts"
RUN_DIR = APP_DIR / ".run"
MODELS_DIR = APP_DIR / "models"
TEST_IMAGES_ROOT = APP_DIR / "test_images"
APP_ENTRY = APP_DIR / "main.py"

IS_WINDOWS = platform.system() == "Windows"

MAIN_APP_PID_FILE = RUN_DIR / "main_app.pid"
RTSP_PUBLISHER_PID_FILE = RUN_DIR / "rtsp_publisher.pid"

START_RTSP_SCRIPT = SCRIPTS_DIR / ("start_mediamtx_rtsp.ps1" if IS_WINDOWS else "start_mediamtx_rtsp.sh")
VIEW_RTSP_SCRIPT = SCRIPTS_DIR / ("rtsp_view.ps1" if IS_WINDOWS else "rtsp_view.sh")