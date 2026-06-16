from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from .config import CONFIG_URL, CONTROL_URL, TEST_IMAGES_URL


def _request_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except error.URLError as e:
        raise RuntimeError(f"Ошибка соединения: {e.reason}") from e

    if not body.strip():
        return {}
    return json.loads(body)


def get_config() -> dict[str, Any]:
    return _request_json(CONFIG_URL)


def patch_config(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(CONFIG_URL, method="PATCH", payload=payload)


def post_control(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(CONTROL_URL, method="POST", payload=payload)


def post_test_images(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json(TEST_IMAGES_URL, method="POST", payload=payload)