from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import api_client
from .config import (
    APP_DIR,
    APP_ENTRY,
    IS_WINDOWS,
    MAIN_APP_PID_FILE,
    MODELS_DIR,
    RTSP_PUBLISHER_PID_FILE,
    START_RTSP_SCRIPT,
    TEST_IMAGES_ROOT,
    VIEW_RTSP_SCRIPT,
)
from .processes import (
    get_venv_python,
    open_process_in_new_terminal_linux,
    open_process_in_new_terminal_windows,
    process_status,
    start_terminal_process,
    stop_managed_process,
)


def pretty_json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def pause() -> None:
    input("\nEnter для продолжения...")


def show_status_lines() -> None:
    rtsp_running, rtsp_pid = process_status(RTSP_PUBLISHER_PID_FILE)
    app_running, app_pid = process_status(MAIN_APP_PID_FILE)

    rtsp_text = f"RUNNING (PID {rtsp_pid})" if rtsp_running else "STOPPED"
    app_text = f"RUNNING (PID {app_pid})" if app_running else "STOPPED"

    print("Статус:")
    print(f"- Симуляция камеры: {rtsp_text}")
    print(f"- MVP-приложение:   {app_text}")

def show_menu() -> None:
    print("\n================ ROAD MONITORING ================")
    show_status_lines()
    print()
    print("Основные действия:")
    print("1) Запустить симуляцию камеры")
    print("2) Запустить MVP-приложение")
    print("3) Открыть просмотр RTSP-видеопотока")
    print("4) Остановить симуляцию камеры")
    print("5) Остановить MVP-приложение")
    print()
    print("Управление MVP:")
    print("6) Выбрать модель детектора")
    print("7) Изменить порог уверенности детектора")
    print("8) Включить/выключить выходной видеопоток MVP")
    print("9) Переключить режим приложения: RTSP/IDLE")
    print("10) Показать текущую конфигурацию")
    print()
    print("Тесты:")
    print("11) Batch-обработка изображений")
    print()
    print("0) Выход")
    print("=================================================")

def start_rtsp() -> None:
    if not START_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {START_RTSP_SCRIPT}")
        return

    start_terminal_process(
        title="RTSP Publisher",
        command=f'"{START_RTSP_SCRIPT}"',
        pid_file=RTSP_PUBLISHER_PID_FILE,
        display_name="Симуляция видеокамеры",
        windows_args=["-File", str(START_RTSP_SCRIPT)],
        cwd=APP_DIR,
    )


def stop_rtsp() -> None:
    stop_managed_process(RTSP_PUBLISHER_PID_FILE, "Симуляция видеокамеры")


def start_app() -> None:
    if not APP_ENTRY.is_file():
        print(f"Файл приложения не найден: {APP_ENTRY}")
        return

    python_exe = get_venv_python()
    if not python_exe.is_file():
        print(f"Python в venv не найден: {python_exe}")
        return

    start_terminal_process(
        title="Main App",
        command=f'"{python_exe}" "{APP_ENTRY}"',
        pid_file=MAIN_APP_PID_FILE,
        display_name="Приложение",
        windows_args=["-Command", f'& "{python_exe}" "{APP_ENTRY}"'],
        cwd=APP_DIR,
    )


def stop_app() -> None:
    stop_managed_process(MAIN_APP_PID_FILE, "Приложение")


def open_viewer() -> None:
    if not VIEW_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {VIEW_RTSP_SCRIPT}")
        return

    if IS_WINDOWS:
        proc = open_process_in_new_terminal_windows(["-File", str(VIEW_RTSP_SCRIPT)])
        if proc is None:
            print("Не найден PowerShell (pwsh/powershell) для запуска нового окна.")
        return

    proc = open_process_in_new_terminal_linux(
        title="RTSP Viewer",
        command=f'"{VIEW_RTSP_SCRIPT}"',
        cwd=APP_DIR,
    )
    if proc is None:
        print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator/xterm)")


def toggle_stream() -> None:
    cfg = api_client.get_config()
    current = cfg.get("stream", {}).get("enable_output_stream")
    next_value = not bool(current)
    resp = api_client.patch_config({"stream": {"enable_output_stream": next_value}})
    print(f"enable_output_stream: {current} -> {next_value}")
    pretty_json(resp)


def change_confidence() -> None:
    raw = input("Введите новое значение confidence_threshold [0..1]: ").strip()
    try:
        value = float(raw)
    except ValueError:
        print("Ошибка: значение должно быть числом.")
        return

    if not (0.0 <= value <= 1.0):
        print("Ошибка: значение должно быть в диапазоне [0, 1].")
        return

    resp = api_client.patch_config({"detector": {"confidence_threshold": value}})
    pretty_json(resp)


def list_model_files() -> list[Path]:
    if not MODELS_DIR.is_dir():
        return []
    allowed_suffixes = {".pt", ".pth", ".onnx", ".engine"}
    files = [p for p in MODELS_DIR.iterdir() if p.is_file() and p.suffix.lower() in allowed_suffixes]
    return sorted(files, key=lambda p: p.name.lower())


def choose_model() -> None:
    models = list_model_files()
    if not MODELS_DIR.is_dir():
        print(f"Папка моделей не найдена: {MODELS_DIR}")
        return
    if not models:
        print(f"В папке {MODELS_DIR} не найдено файлов моделей.")
        return

    cfg = api_client.get_config()
    current_model = cfg.get("detector", {}).get("model_path")

    print("\nДоступные модели:")
    for idx, model_path in enumerate(models, start=1):
        rel_path = f"models/{model_path.name}"
        marker = " [текущая]" if rel_path == current_model else ""
        print(f"{idx}) {model_path.name}{marker}")
    print("0) Назад")

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

    selected = models[index - 1]
    rel_path = f"models/{selected.name}"
    resp = api_client.patch_config({"detector": {"model_path": rel_path}})
    pretty_json(resp)

def switch_video_mode() -> None:
    print()
    print("1) RTSP")
    print("2) IDLE")
    choice = input("Выберите режим приложения: ").strip()

    if choice == "1":
        mode = "rtsp"
    elif choice == "2":
        mode = "idle"
    else:
        print("Некорректный выбор")
        return

    resp = api_client.post_control({"mode": mode})
    print(f"Режим приложения переключён на: {mode}")
    pretty_json(resp)


def show_config() -> None:
    cfg = api_client.get_config()
    pretty_json(cfg)


def list_test_image_dirs() -> list[Path]:
    if not TEST_IMAGES_ROOT.is_dir():
        return []
    dirs = [p for p in TEST_IMAGES_ROOT.iterdir() if p.is_dir() and p.name.lower() != "output"]
    return sorted(dirs, key=lambda p: p.name.lower())


def run_batch() -> None:
    test_dirs = list_test_image_dirs()
    if not TEST_IMAGES_ROOT.is_dir():
        print(f"Папка test_images не найдена: {TEST_IMAGES_ROOT}")
        return
    if not test_dirs:
        print(f"В папке {TEST_IMAGES_ROOT} не найдено подпапок с изображениями.")
        return

    cfg = api_client.get_config()
    detector_conf = cfg.get("detector", {}).get("confidence_threshold", "n/a")
    model_path = cfg.get("detector", {}).get("model_path", "n/a")

    print("\nДоступные папки в test_images:")
    for idx, folder in enumerate(test_dirs, start=1):
        print(f"{idx}) {folder.name}")
    print("0) Назад")
    print()
    print("Текущие параметры детекции:")
    print(f"- detector.confidence_threshold: {detector_conf}")
    print(f"- detector.model_path          : {model_path}")

    choice = input("Выберите папку для batch-обработки: ").strip()
    if choice == "0":
        return
    if not choice.isdigit():
        print("Некорректный выбор")
        return

    index = int(choice)
    if not (1 <= index <= len(test_dirs)):
        print("Некорректный выбор")
        return

    selected_dir = test_dirs[index - 1]
    fps_raw = input("Введите fps для batch [по умолчанию 5]: ").strip()
    if fps_raw == "":
        fps = 5
    else:
        try:
            fps = int(fps_raw)
        except ValueError:
            print("Ошибка: fps должен быть целым числом.")
            return

    if fps <= 0:
        print("Ошибка: fps должен быть больше 0.")
        return

    timestamp = datetime.now().strftime("output_%Y-%m-%d_%H-%M-%S")
    output_dir = selected_dir / timestamp

    payload = {
        "input_dir": str(selected_dir),
        "output_dir": str(output_dir),
        "fps": fps,
    }
    resp = api_client.post_test_images(payload)
    pretty_json(resp)
    print(f"Результаты будут сохранены в: {output_dir}")


def run_cli() -> None:
    actions = {
        "1": start_rtsp,
        "2": start_app,
        "3": open_viewer,
        "4": stop_rtsp,
        "5": stop_app,
        "6": choose_model,
        "7": change_confidence,
        "8": toggle_stream,
        "9": switch_video_mode,
        "10": show_config,
        "11": run_batch,
    }

    while True:
        show_menu()
        choice = input("Выбор: ").strip()

        if choice == "0":
            print("Выход.")
            return

        action = actions.get(choice)
        if action is None:
            print("Неизвестный выбор.")
            pause()
            continue

        try:
            action()
        except Exception as e:
            print(f"Ошибка: {e}")
            pause()
            continue

        if choice == "10":
            pause()