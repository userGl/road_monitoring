# dev/tracker_menu.py
from __future__ import annotations
from typing import Optional

from core import runtime_state

def _read_int(prompt: str, current: int, min_value: int | None = None) -> int:
    raw = input(f"{prompt} [{current}]: ").strip()
    if not raw:
        return current

    try:
        value = int(raw)
    except ValueError:
        print("[dev] Некорректное целое число, значение не изменено")
        return current

    if min_value is not None and value < min_value:
        print(f"[dev] Значение должно быть >= {min_value}, значение не изменено")
        return current

    return value


def _read_float(
    prompt: str,
    current: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    raw = input(f"{prompt} [{current}]: ").strip()
    if not raw:
        return current

    try:
        value = float(raw)
    except ValueError:
        print("[dev] Некорректное число, значение не изменено")
        return current

    if min_value is not None and value < min_value:
        print(f"[dev] Значение должно быть >= {min_value}, значение не изменено")
        return current

    if max_value is not None and value > max_value:
        print(f"[dev] Значение должно быть <= {max_value}, значение не изменено")
        return current

    return value


def _read_bool(prompt: str, current: bool) -> bool:
    current_str = "on" if current else "off"
    raw = input(f"{prompt} [on/off, текущее={current_str}]: ").strip().lower()
    if not raw:
        return current

    if raw in ("1", "true", "on", "yes", "y", "да", "д"):
        return True

    if raw in ("0", "false", "off", "no", "n", "нет", "н"):
        return False

    print("[dev] Некорректное булево значение, значение не изменено")
    return current


def print_tracker_settings() -> None:
    tracker_stage = getattr(runtime_state, "tracker_stage", None)
    if tracker_stage is None:
        print("[dev] tracker_stage недоступен")
        return

    tracker = tracker_stage.tracker

    print()
    print("============= TRACKER SETTINGS (DEV) =============")
    print(f"1) confirm_hits            = {tracker.confirm_hits}")
    print(f"2) max_misses              = {tracker.max_misses}")
    print(f"3) min_match_score         = {tracker.min_match_score}")
    print(f"4) new_track_min_conf      = {tracker.new_track_min_conf}")
    print(f"5) use_motion_compensation = {tracker.use_motion_compensation}")
    print("6) reset() tracker state")
    print("0) Назад")
    print("==================================================")


def tracker_settings_menu() -> None:
    while True:
        tracker_stage = getattr(runtime_state, "tracker_stage", None)
        if tracker_stage is None:
            print("[dev] Трекер недоступен: tracker_stage ещё не создан")
            return

        tracker = tracker_stage.tracker
        print_tracker_settings()

        action = input("Выбор: ").strip()

        if action == "1":
            tracker.confirm_hits = _read_int(
                "Новое значение confirm_hits",
                tracker.confirm_hits,
                min_value=1,
            )
            print(f"[dev] confirm_hits = {tracker.confirm_hits}")

        elif action == "2":
            tracker.max_misses = _read_int(
                "Новое значение max_misses",
                tracker.max_misses,
                min_value=0,
            )
            print(f"[dev] max_misses = {tracker.max_misses}")

        elif action == "3":
            tracker.min_match_score = _read_float(
                "Новое значение min_match_score",
                tracker.min_match_score,
                min_value=0.0,
                max_value=1.0,
            )
            print(f"[dev] min_match_score = {tracker.min_match_score}")

        elif action == "4":
            tracker.new_track_min_conf = _read_float(
                "Новое значение new_track_min_conf",
                tracker.new_track_min_conf,
                min_value=0.0,
                max_value=1.0,
            )
            print(f"[dev] new_track_min_conf = {tracker.new_track_min_conf}")

        elif action == "5":
            tracker.use_motion_compensation = _read_bool(
                "use_motion_compensation",
                tracker.use_motion_compensation,
            )
            print(
                "[dev] use_motion_compensation = "
                f"{tracker.use_motion_compensation}"
            )

        elif action == "6":
            tracker.reset()
            print("[dev] tracker.reset() выполнен")

        elif action == "0":
            break

        else:
            print("[dev] Неизвестная команда")

def main() -> None:
    tracker_settings_menu()


if __name__ == "__main__":
    main()