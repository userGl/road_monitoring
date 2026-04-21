from typing import Optional

from . import actions, api
from .paths import MAIN_APP_PID_FILE, RTSP_PUBLISHER_PID_FILE, START_RTSP_SCRIPT, VIEW_RTSP_SCRIPT
from .runtime import is_managed_process_running, read_pid_file


def pretty_print_json(cfg: dict) -> None:
    import json
    print(json.dumps(cfg, indent=2, ensure_ascii=False))


def print_config(cfg: dict) -> None:
    stream_enabled = cfg.get("stream", {}).get("enable_output_stream", "n/a")
    detector_conf = cfg.get("detector", {}).get("confidence_threshold", "n/a")
    model_path = cfg.get("detector", {}).get("model_path", "n/a")

    print()
    print("================ CURRENT CONFIG ================")
    print(f"stream.enable_output_stream : {stream_enabled}")
    print(f"detector.confidence_threshold: {detector_conf}")
    print(f"detector.model_path          : {model_path}")
    print("===============================================")
    print()


def print_control_status(status: Optional[dict]) -> None:
    print()
    print("================ CURRENT CONTROL ===============")
    if status is None:
        print("mode             : n/a")
        print("test_input_dir   : n/a")
        print("test_output_dir  : n/a")
        print("test_fps         : n/a")
        print("yolo_stage_ready : n/a")
    else:
        print(f"mode             : {status.get('mode', 'n/a')}")
        print(f"test_input_dir   : {status.get('test_input_dir', 'n/a')}")
        print(f"test_output_dir  : {status.get('test_output_dir', 'n/a')}")
        print(f"test_fps         : {status.get('test_fps', 'n/a')}")
        print(f"yolo_stage_ready : {status.get('yolo_stage_ready', 'n/a')}")
    print("===============================================")
    print()


def pause(msg: str = "Нажми Enter, чтобы продолжить...") -> None:
    input(msg)


def app_mode_menu(cfg: dict) -> None:
    while True:
        status = api.load_control_status()
        print_control_status(status)

        print("============= РЕЖИМ ПРИЛОЖЕНИЯ =============")
        print("1) Включить режим idle")
        print("2) Включить режим rtsp")
        print("3) Запустить batch image")
        print("0) Назад")
        print("============================================")
        print()

        action = input("Выбор: ").strip()

        if action == "1":
            actions.post_control_mode("idle")
            pause()
        elif action == "2":
            actions.post_control_mode("rtsp")
            pause()
        elif action == "3":
            actions.run_batch_images(cfg)
            pause()
        elif action == "0":
            break
        else:
            print("Некорректный выбор")


def process_control_menu() -> None:
    rtsp_label = START_RTSP_SCRIPT.name
    viewer_label = VIEW_RTSP_SCRIPT.name

    while True:
        main_pid = read_pid_file(MAIN_APP_PID_FILE) if is_managed_process_running(MAIN_APP_PID_FILE) else None
        rtsp_pid = read_pid_file(RTSP_PUBLISHER_PID_FILE) if is_managed_process_running(RTSP_PUBLISHER_PID_FILE) else None

        print()
        print("=========== УПРАВЛЕНИЕ ПРОЦЕССАМИ ===========")
        print(f"1) Запустить симуляцию видеокамеры ({rtsp_label})" + (f" [RUNNING PID {rtsp_pid}]" if rtsp_pid else ""))
        print(f"2) Запустить приложение (main.py в venv)" + (f" [RUNNING PID {main_pid}]" if main_pid else ""))
        print("3) Вкл/выкл RTSP output (stream.enable_output_stream)")
        print(f"4) Запустить просмотр RTSP потока ({viewer_label} / mpv)")
        print("5) Остановить симуляцию видеокамеры")
        print("6) Остановить приложение")
        print("0) Назад")
        print("=============================================")
        print()

        action = input("Выбор: ").strip()

        if action == "1":
            actions.start_rtsp_publisher()
        elif action == "2":
            actions.start_main_app()
        elif action == "3":
            cfg = api.load_config()
            if cfg is None:
                print("API недоступно, изменить stream.enable_output_stream нельзя.")
            else:
                actions.change_stream(cfg)
        elif action == "4":
            actions.start_rtsp_viewer()
        elif action == "5":
            actions.stop_rtsp_publisher()
        elif action == "6":
            actions.stop_main_app()
        elif action == "0":
            break
        else:
            print("Некорректный выбор")


def main_loop() -> None:
    while True:
        cfg = api.load_config()

        if cfg is None:
            print("Открою меню управления процессами — оттуда можно запустить приложение.")
            process_control_menu()
            continue

        print_config(cfg)
        print("Что сделать?")
        print("1) Управление процессами")
        print("2) Режим приложения")
        print("3) Изменить detector.confidence_threshold")
        print("4) Изменить detector.model_path")
        print("5) Показать полный JSON")
        print("0) Выход")
        print()

        action = input("Выбор: ").strip()

        if action == "1":
            process_control_menu()
        elif action == "2":
            app_mode_menu(cfg)
        elif action == "3":
            actions.change_confidence(cfg)
        elif action == "4":
            actions.change_model_path(cfg)
        elif action == "5":
            pretty_print_json(cfg)
            pause()
        elif action == "0":
            print("Выход")
            break
        else:
            print("Некорректный выбор")