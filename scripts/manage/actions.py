from datetime import datetime
from pathlib import Path

from . import api
from .paths import (
    APP_DIR,
    APP_ENTRY,
    MAIN_APP_PID_FILE,
    MODELS_DIR,
    RTSP_PUBLISHER_PID_FILE,
    START_RTSP_SCRIPT,
    TEST_IMAGES_ROOT,
    VIEW_RTSP_SCRIPT,
    IS_WINDOWS,
)
from .runtime import (
    get_venv_python,
    is_managed_process_running,
    open_process_in_new_terminal_linux,
    open_process_in_new_terminal_windows,
    read_pid_file,
    stop_managed_process,
    write_pid_file,
)


def pretty_print_json(cfg: dict) -> None:
    import json
    print(json.dumps(cfg, indent=2, ensure_ascii=False))


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
        resp = api.patch_config(payload)
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
        resp = api.patch_config(payload)
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
        resp = api.patch_config(payload)
    except Exception as e:
        print(f"Ошибка PATCH-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()


def post_control_mode(mode: str) -> None:
    payload = {"mode": mode}
    print("\nОтправка POST /control...")
    try:
        resp = api.post_control(payload)
    except Exception as e:
        print(f"Ошибка POST-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()


def list_test_image_dirs() -> list[Path]:
    if not TEST_IMAGES_ROOT.is_dir():
        return []

    dirs = [
        path for path in TEST_IMAGES_ROOT.iterdir()
        if path.is_dir() and path.name.lower() != "output"
    ]
    return sorted(dirs, key=lambda p: p.name.lower())


def run_batch_images(cfg: dict) -> None:
    test_dirs = list_test_image_dirs()

    if not TEST_IMAGES_ROOT.is_dir():
        print(f"Папка test_images не найдена: {TEST_IMAGES_ROOT}")
        return

    if not test_dirs:
        print(f"В папке {TEST_IMAGES_ROOT} не найдено подпапок с изображениями.")
        return

    detector_conf = cfg.get("detector", {}).get("confidence_threshold", "n/a")
    model_path = cfg.get("detector", {}).get("model_path", "n/a")

    print()
    print("Доступные папки в test_images:")
    for idx, folder in enumerate(test_dirs, start=1):
        print(f"{idx}) {folder.name}")
    print("0) Назад")
    print()
    print("Текущие параметры детекции:")
    print(f"- detector.confidence_threshold: {detector_conf}")
    print(f"- detector.model_path          : {model_path}")
    print()

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

    print("\nОтправка POST /test/images...")
    try:
        resp = api.post_test_images(payload)
    except Exception as e:
        print(f"Ошибка POST-запроса: {e}")
        return

    print("Ответ API:")
    pretty_print_json(resp)
    print()
    print(f"Результаты будут сохранены в: {output_dir}")
    print()


def start_rtsp_publisher() -> None:
    if is_managed_process_running(RTSP_PUBLISHER_PID_FILE):
        pid = read_pid_file(RTSP_PUBLISHER_PID_FILE)
        print(f"Симуляция видеокамеры уже запущена (PID {pid}).")
        return

    if not START_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {START_RTSP_SCRIPT}")
        return

    if IS_WINDOWS:
        proc = open_process_in_new_terminal_windows(["-File", str(START_RTSP_SCRIPT)])
        if proc is None:
            print("Не найден PowerShell (pwsh/powershell) для запуска нового окна.")
            return
    else:
        proc = open_process_in_new_terminal_linux("RTSP Publisher", f'"{START_RTSP_SCRIPT}"')
        if proc is None:
            print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator/xterm)")
            return

    write_pid_file(RTSP_PUBLISHER_PID_FILE, proc.pid)
    print(f"Симуляция видеокамеры запущена (PID {proc.pid}).")


def start_rtsp_viewer() -> None:
    if not VIEW_RTSP_SCRIPT.is_file():
        print(f"Скрипт не найден: {VIEW_RTSP_SCRIPT}")
        return

    if IS_WINDOWS:
        proc = open_process_in_new_terminal_windows(["-File", str(VIEW_RTSP_SCRIPT)])
        if proc is None:
            print("Не найден PowerShell (pwsh/powershell) для запуска нового окна.")
        return

    proc = open_process_in_new_terminal_linux("RTSP Viewer", f'"{VIEW_RTSP_SCRIPT}"')
    if proc is None:
        print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator/xterm)")


def start_main_app() -> None:
    if is_managed_process_running(MAIN_APP_PID_FILE):
        pid = read_pid_file(MAIN_APP_PID_FILE)
        print(f"Приложение уже запущено (PID {pid}).")
        return

    if not APP_ENTRY.is_file():
        print(f"Файл приложения не найден: {APP_ENTRY}")
        return

    python_exe = get_venv_python()
    if not python_exe.is_file():
        print(f"Python в venv не найден: {python_exe}")
        return

    if IS_WINDOWS:
        proc = open_process_in_new_terminal_windows([
            "-Command",
            f'& "{python_exe}" "{APP_ENTRY}"',
        ])
        if proc is None:
            print("Не найден PowerShell (pwsh/powershell) для запуска нового окна.")
            return
    else:
        command = f'cd "{APP_DIR}" && "{python_exe}" "{APP_ENTRY}"'
        proc = open_process_in_new_terminal_linux("Main App", command)
        if proc is None:
            print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator/xterm)")
            return

    write_pid_file(MAIN_APP_PID_FILE, proc.pid)
    print(f"Приложение запущено (PID {proc.pid}).")


def stop_rtsp_publisher() -> None:
    stop_managed_process(RTSP_PUBLISHER_PID_FILE, "Симуляция видеокамеры")


def stop_main_app() -> None:
    stop_managed_process(MAIN_APP_PID_FILE, "Приложение")
