import os
import signal
import subprocess
from pathlib import Path
from shutil import which
from typing import Optional

from .paths import APP_DIR, IS_WINDOWS, RUN_DIR


def ensure_run_dir() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)


def write_pid_file(pid_file: Path, pid: int) -> None:
    ensure_run_dir()
    pid_file.write_text(str(pid), encoding="utf-8")


def read_pid_file(pid_file: Path) -> Optional[int]:
    if not pid_file.is_file():
        return None
    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def remove_pid_file(pid_file: Path) -> None:
    try:
        pid_file.unlink(missing_ok=True)
    except Exception:
        pass


def get_powershell_exe() -> Optional[str]:
    return which("pwsh") or which("powershell") or which("powershell.exe")


def get_venv_python() -> Path:
    if IS_WINDOWS:
        return APP_DIR / ".venv" / "Scripts" / "python.exe"
    return APP_DIR / ".venv" / "bin" / "python"


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if IS_WINDOWS:
        ps_exe = get_powershell_exe()
        if not ps_exe:
            return False

        script = "\n".join([
            "$pidValue = [int]$args[0]",
            '$p = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue',
            "if ($null -ne $p) { exit 0 }",
            "exit 1",
        ])

        result = subprocess.run(
            [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script, str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def is_managed_process_running(pid_file: Path) -> bool:
    pid = read_pid_file(pid_file)
    if pid is None:
        return False

    if is_pid_running(pid):
        return True

    remove_pid_file(pid_file)
    return False


def stop_process_by_pid(pid: int) -> bool:
    if pid <= 0:
        return False

    if IS_WINDOWS:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0

    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def stop_managed_process(pid_file: Path, name: str) -> None:
    pid = read_pid_file(pid_file)
    if pid is None:
        print(f"{name}: PID-файл отсутствует.")
        return

    if not is_pid_running(pid):
        remove_pid_file(pid_file)
        print(f"{name}: процесс уже не запущен, stale PID удалён.")
        return

    if stop_process_by_pid(pid):
        remove_pid_file(pid_file)
        print(f"{name} остановлен (PID {pid}).")
    else:
        print(f"Не удалось остановить {name} (PID {pid}).")


def open_process_in_new_terminal_linux(title: str, command: str) -> Optional[subprocess.Popen]:
    tail = "echo; read -n 1 -s -r -p 'Нажми любую клавишу для закрытия...'"
    full_cmd = f"{command}; {tail}"

    if which("gnome-terminal"):
        return subprocess.Popen([
            "gnome-terminal",
            f"--title={title}",
            "--",
            "bash",
            "-lc",
            full_cmd,
        ])

    if which("x-terminal-emulator"):
        return subprocess.Popen([
            "x-terminal-emulator",
            "-e",
            "bash",
            "-lc",
            full_cmd,
        ])

    if which("xterm"):
        return subprocess.Popen([
            "xterm",
            "-T",
            title,
            "-e",
            "bash",
            "-lc",
            full_cmd,
        ])

    return None


def open_process_in_new_terminal_windows(args: list[str]) -> Optional[subprocess.Popen]:
    ps_exe = get_powershell_exe()
    if not ps_exe:
        return None

    cmd = [ps_exe, "-NoExit", "-ExecutionPolicy", "Bypass", *args]
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(cmd, cwd=str(APP_DIR), creationflags=creationflags)
