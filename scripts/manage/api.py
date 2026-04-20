import json
from typing import Optional
import urllib.error
import urllib.request

from .paths import CONFIG_URL, CONTROL_URL, TEST_IMAGES_URL


def http_get(url: str) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        return resp.read().decode("utf-8")


def http_patch_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="PATCH",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_config() -> Optional[dict]:
    try:
        raw = http_get(CONFIG_URL)
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print()
        print(f"Не удалось получить текущую конфигурацию: {CONFIG_URL}")
        print(f"Причина: {e}")
        return None


def load_control_status() -> Optional[dict]:
    try:
        raw = http_get(CONTROL_URL)
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print()
        print(f"Не удалось получить текущий статус управления: {CONTROL_URL}")
        print(f"Причина: {e}")
        return None


def patch_config(payload: dict) -> dict:
    return http_patch_json(CONFIG_URL, payload)


def post_control(payload: dict) -> dict:
    return http_post_json(CONTROL_URL, payload)


def post_test_images(payload: dict) -> dict:
    return http_post_json(TEST_IMAGES_URL, payload)
