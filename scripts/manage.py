#!/usr/bin/env python
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import urllib.error
import urllib.request


BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8081/api/v1")
CONFIG_URL = f"{BASE_URL}/config"

SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent

START_RTSP_SCRIPT = SCRIPT_DIR / "start_mediamtx_rtsp.sh"
VIEW_RTSP_SCRIPT = SCRIPT_DIR / "rtsp_view.sh"
APP_ENTRY = APP_DIR / "main.py"
MODELS_DIR = APP_DIR / "models"


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


def load_config() -> Optional[dict]:
    try:
        raw = http_get(CONFIG_URL)
        return json.loads(raw)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print()
        print(f"Не удалось получить текущую конфигурацию: {CONFIG_URL}")
        print(f"Причина: {e}")
        return None


def print_config(cfg: dict) -> None:
    stream_enabled = cfg.get("stream", {}).get("enable_output_stream", "n/a")
    detector_conf = cfg.get("detector", {}).get("confidence_threshold", "n/a")
    model_path = cfg.get("detector", {}).get("model_path", "n/a")

    print()
    print("================ CURRENT CONFIG ================")
    print(f"stream.enable_output_stream  : {stream_enabled}")
    print(f"detector.confidence_threshold: {detector_conf}")
    print(f"detector.model_path          : {model_path}")
    print("===============================================")
    print()


def pretty_print_json(cfg: dict) -> None:
    print(json.dumps(cfg, indent=2, ensure_ascii=False))


def pause(msg: str = "Нажми Enter, чтобы продолжить...") -> None:
    input(msg)


def change_confidence(cfg: dict) -> None:
    raw = input("Введите новое значение confidence_threshold [0..1]: ").strip()
    try:
        value = float(raw)
    except ValueError:
        print("Ошибка: значение должно быть числом.")
        return

    if not (0.0 <= value <= 1.0):
        print("Ошибка: значение должно быть в диапазоне [0, 1].")
        return

    payload = {"detector": {"confidence_threshold": value}}
    print("\nОтправка PATCH...")
    try:
        resp = http_patch_json(CONFIG_URL, payload)
    except Exception as e:
        print(f"Ошибка PATCH-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()


def change_stream(cfg: dict) -> None:
    print()
    print("1) true")
    print("2) false")
    choice = input("Выберите новое значение enable_output_stream: ").strip()

    if choice == "1":
        value = True
    elif choice == "2":
        value = False
    else:
        print("Некорректный выбор")
        return

    payload = {"stream": {"enable_output_stream": value}}
    print("\nОтправка PATCH...")
    try:
        resp = http_patch_json(CONFIG_URL, payload)
    except Exception as e:
        print(f"Ошибка PATCH-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()


def list_model_files() -> list[Path]:
    if not MODELS_DIR.is_dir():
        return []

    allowed_suffixes = {".pt", ".pth", ".onnx", ".engine"}
    files = [
        path for path in MODELS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in allowed_suffixes
    ]
    return sorted(files, key=lambda p: p.name.lower())


def change_model_path(cfg: dict) -> None:
    models = list_model_files()

    if not MODELS_DIR.is_dir():
        print(f"Папка моделей не найдена: {MODELS_DIR}")
        return

    if not models:
        print(f"В папке {MODELS_DIR} не найдено файлов моделей.")
        return

    current_model = cfg.get("detector", {}).get("model_path")

    print()
    print("Доступные модели:")
    for idx, model_path in enumerate(models, start=1):
        rel_path = f"models/{model_path.name}"
        marker = " [текущая]" if rel_path == current_model else ""
        print(f"{idx}) {model_path.name}{marker}")
    print("0) Назад")
    print()

    choice = input("Выберите модель: ").strip()

    if choice == "0":
        return

    if not choice.isdigit():
        print("Некорректный выбор")
        return

    index = int(choice)
    if not (1 <= index <= len(models)):
        print("Некорректный выбор")
        return

    selected_model = models[index - 1]
    selected_rel_path = f"models/{selected_model.name}"

    payload = {"detector": {"model_path": selected_rel_path}}
    print("\nОтправка PATCH...")
    try:
        resp = http_patch_json(CONFIG_URL, payload)
    except Exception as e:
        print(f"Ошибка PATCH-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()


def shutil_which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)


def open_in_new_terminal(title: str, command: str) -> None:
    tail = "echo; read -n 1 -s -r -p 'Нажми любую клавишу для закрытия...'"
    full_cmd = f"{command}; {tail}"

    if shutil_which("gnome-terminal"):
        subprocess.Popen(
            [
                "gnome-terminal",
                f"--title={title}",
                "--",
                "bash",
                "-lc",
                full_cmd,
            ]
        )
        return

    if shutil_which("x-terminal-emulator"):
        subprocess.Popen(
            [
                "x-terminal-emulator",
                "-e",
                "bash",
                "-lc",
                full_cmd,
            ]
        )
        return

    print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator)")


def is_process_running(pattern: str) -> bool:
    try:
        out = subprocess.run(
            ["ps", "aux"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        ).stdout
    except Exception:
        return False

    for line in out.splitlines():
        if pattern in line and "manage.py" not in line:
            return True
    return False


def start_rtsp_publisher() -> None:
    pattern = str(START_RTSP_SCRIPT)
    if is_process_running(pattern):
        print(f"Симуляция видеокамеры уже запущена (найден процесс с {pattern}).")
        return

    if not START_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {START_RTSP_SCRIPT}")
        return

    cmd = f'"{START_RTSP_SCRIPT}"'
    open_in_new_terminal("RTSP Publisher", cmd)


def start_rtsp_viewer() -> None:
    if not VIEW_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {VIEW_RTSP_SCRIPT}")
        return

    cmd = f'"{VIEW_RTSP_SCRIPT}"'
    open_in_new_terminal("RTSP Viewer", cmd)


def start_main_app() -> None:
    pattern = str(APP_ENTRY)
    if is_process_running(pattern):
        print(f"Приложение уже запущено (найден процесс с {pattern}).")
        return

    if not APP_ENTRY.is_file():
        print(f"Файл приложения не найден: {APP_ENTRY}")
        return

    venv_activate = APP_DIR / ".venv" / "bin" / "activate"
    if not venv_activate.is_file():
        print(f"Файл активации venv не найден: {venv_activate}")
        return

    cmd = (
        f'cd "{APP_DIR}" && '
        f'source "{venv_activate}" && '
        f'python "{APP_ENTRY}"'
    )
    open_in_new_terminal("Main App", cmd)


def launch_menu() -> None:
    while True:
        print()
        print("============== УПРАВЛЕНИЕ ЗАПУСКОМ ==============")
        print("1) Запустить симуляцию видеокамеры (start_mediamtx_rtsp.sh)")
        print("2) Запустить приложение (main.py в venv)")
        print("3) Вкл/выкл RTSP output (stream.enable_output_stream)")
        print("4) Запустить просмотр RTSP потока (rtsp_view.sh / mpv)")
        print("0) Назад")
        print("===============================================")
        print()

        action = input("Выбор: ").strip()

        if action == "1":
            start_rtsp_publisher()
        elif action == "2":
            start_main_app()
        elif action == "3":
            cfg = load_config()
            if cfg is None:
                print("API недоступно, изменить stream.enable_output_stream нельзя.")
            else:
                change_stream(cfg)
        elif action == "4":
            start_rtsp_viewer()
        elif action == "0":
            break
        else:
            print("Некорректный выбор")


def main_loop() -> None:
    while True:
        cfg = load_config()

        if cfg is None:
            print("Открою меню управления запуском — оттуда можно запустить приложение.")
            launch_menu()
            continue

        print_config(cfg)
        print("Что сделать?")
        print("1) Управление запуском")
        print("2) Изменить detector.confidence_threshold")
        print("3) Изменить detector.model_path")
        print("4) Показать полный JSON")
        print("0) Выход")
        print()

        action = input("Выбор: ").strip()

        if action == "1":
            launch_menu()
        elif action == "2":
            change_confidence(cfg)
        elif action == "3":
            change_model_path(cfg)
        elif action == "4":
            pretty_print_json(cfg)
            pause()
        elif action == "0":
            print("Выход")
            break
        else:
            print("Некорректный выбор")


def main() -> None:
    main_loop()


if __name__ == "__main__":
    main()