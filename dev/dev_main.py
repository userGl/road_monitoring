from __future__ import annotations

import threading

from core.runtime_config import init_app_config_from_file, get_current_app_settings
from core import runtime_state

from services.rtsp_session import run_rtsp_session
from services.images_batch import run_images_batch_session
from dev.tracker_menu import tracker_settings_menu


def _run_rtsp_in_thread() -> threading.Thread:
    settings = get_current_app_settings()

    with runtime_state.mode_lock:
        runtime_state.mode = "rtsp"

    thread = threading.Thread(
        target=run_rtsp_session,
        kwargs={
            "cfg": settings["cfg"],
            "input_rtsp_url": settings["input_rtsp_url"],
            "output_rtsp_url": settings["output_rtsp_url"],
            "use_hwaccel": settings["use_hwaccel"],
            "model_input_width": settings["model_input_width"],
            "model_input_height": settings["model_input_height"],
            "model_path": settings["model_path"],
            "detector_conf": settings["detector_conf"],
        },
        daemon=True,
    )
    thread.start()
    return thread


def _run_images_batch() -> None:
    input_dir = input("input_dir: ").strip()
    if not input_dir:
        print("[dev] input_dir пустой")
        return

    output_dir = input("output_dir: ").strip()
    if not output_dir:
        print("[dev] output_dir пустой")
        return

    raw_fps = input("fps [5]: ").strip()
    if not raw_fps:
        fps = 5
    else:
        try:
            fps = int(raw_fps)
        except ValueError:
            print("[dev] Некорректный fps")
            return

    settings = get_current_app_settings()

    with runtime_state.mode_lock:
        runtime_state.mode = "test_images"
        runtime_state.test_input_dir = input_dir
        runtime_state.test_output_dir = output_dir
        runtime_state.test_fps = fps

    run_images_batch_session(
        input_dir=input_dir,
        output_dir=output_dir,
        fps=fps,
        cfg=settings["cfg"],
        model_path=settings["model_path"],
        detector_conf=settings["detector_conf"],
    )

    with runtime_state.mode_lock:
        runtime_state.mode = "idle"


def _stop_rtsp() -> None:
    with runtime_state.mode_lock:
        runtime_state.mode = "idle"
    print("[dev] Запрошена остановка RTSP-сессии")


def _print_status(rtsp_thread: threading.Thread | None) -> None:
    tracker_stage = getattr(runtime_state, "tracker_stage", None)
    tracker_ready = tracker_stage is not None

    with runtime_state.mode_lock:
        mode = getattr(runtime_state, "mode", "idle")

    print()
    print("================ DEV MAIN MENU ================")
    print(f"mode: {mode}")
    print(f"rtsp_thread_alive: {rtsp_thread.is_alive() if rtsp_thread else False}")
    print(f"tracker_ready: {tracker_ready}")
    print("1) Запустить RTSP-сессию")
    print("2) Остановить RTSP-сессию")
    print("3) Запустить batch по изображениям")
    print("4) Настройки трекера")
    print("0) Выход")
    print("===============================================")


def main() -> None:
    init_app_config_from_file()

    if not hasattr(runtime_state, "mode"):
        runtime_state.mode = "idle"

    if not hasattr(runtime_state, "tracker_stage"):
        runtime_state.tracker_stage = None

    if not hasattr(runtime_state, "yolo_stage"):
        runtime_state.yolo_stage = None

    if not hasattr(runtime_state, "test_input_dir"):
        runtime_state.test_input_dir = None

    if not hasattr(runtime_state, "test_output_dir"):
        runtime_state.test_output_dir = None

    if not hasattr(runtime_state, "test_fps"):
        runtime_state.test_fps = None

    rtsp_thread: threading.Thread | None = None

    while True:
        _print_status(rtsp_thread)
        action = input("Выбор: ").strip()

        if action == "1":
            if rtsp_thread is not None and rtsp_thread.is_alive():
                print("[dev] RTSP-сессия уже запущена")
                continue

            rtsp_thread = _run_rtsp_in_thread()
            print("[dev] RTSP-сессия запущена")

        elif action == "2":
            _stop_rtsp()

        elif action == "3":
            _run_images_batch()

        elif action == "4":
            tracker_settings_menu()

        elif action == "0":
            _stop_rtsp()
            break

        else:
            print("[dev] Неизвестная команда")


if __name__ == "__main__":
    main()