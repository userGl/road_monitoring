# from pathlib import Path
# import os

# BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8081/api/v1")
# CONFIG_URL = f"{BASE_URL}/config"
# CONTROL_URL = f"{BASE_URL}/control"
# TEST_IMAGES_URL = f"{BASE_URL}/test/images"

# PACKAGE_DIR = Path(__file__).resolve().parent.parent
# APP_DIR = PACKAGE_DIR.parent
# APP_ENTRY = APP_DIR / "main.py"
# MODELS_DIR = APP_DIR / "models"
# TEST_IMAGES_ROOT = APP_DIR / "test_images"


from pathlib import Path
import os
import yaml


SCRIPTS_DIR = Path(__file__).resolve().parent.parent
APP_DIR = SCRIPTS_DIR.parent

CONFIG_PATH = SCRIPTS_DIR / "scripts_config.yaml"

if not CONFIG_PATH.exists():
    raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}


def env_or_cfg(env_name: str, cfg_key: str, default=None):
    return os.environ.get(env_name, cfg.get(cfg_key, default))


mvp_control_ip = env_or_cfg("MVP_CONTROL_IP", "mvp_control_ip", "127.0.0.1")
mvp_control_port = env_or_cfg("MVP_CONTROL_PORT", "mvp_control_port", 8081)

BASE_URL = os.environ.get(
    "BASE_URL",
    f"http://{mvp_control_ip}:{mvp_control_port}/api/v1"
)

CONFIG_URL = f"{BASE_URL}/config"
CONTROL_URL = f"{BASE_URL}/control"
TEST_IMAGES_URL = f"{BASE_URL}/test/images"

MODELS_DIR = APP_DIR / "models"
TEST_IMAGES_ROOT = APP_DIR / "test_images"