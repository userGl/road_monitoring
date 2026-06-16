from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from shutil import which
from typing import Optional

from .config import APP_DIR, IS_WINDOWS, RUN_DIR


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
    except (OSError, ValueError):
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


def process_status(pid_file: Path) -> tuple[bool, Optional[int]]:
    pid = read_pid_file(pid_file)
    if pid is None:
        return False, None
    if is_pid_running(pid):
        return True, pid
    remove_pid_file(pid_file)
    return False, None


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
        pgid = os.getpgid(pid)
    except OSError:
        return False

    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return False

    deadline = time.time() + 3.0
    while time.time() < deadline:
        if not is_pid_running(pid):
            return True
        time.sleep(0.1)

    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass

    return not is_pid_running(pid)


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


def wait_for_pid_file(pid_file: Path, timeout: float = 5.0) -> Optional[int]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = read_pid_file(pid_file)
        if pid and pid > 0:
            return pid
        time.sleep(0.1)
    return None


def _build_linux_terminal_command(command: str, pid_file: Path) -> str:
    return (
        f'echo $$ > "{pid_file}"; '
        f'{command}; '
        f'echo; '
        f'read -n 1 -s -r -p \'Нажми любую клавишу для закрытия...\''
    )


def open_process_in_new_terminal_linux(
    title: str,
    command: str,
    pid_file: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Optional[subprocess.Popen]:
    working_dir = str(cwd or APP_DIR)
    full_cmd = command

    if pid_file is not None:
        ensure_run_dir()
        remove_pid_file(pid_file)
        full_cmd = _build_linux_terminal_command(command, pid_file)

    if which("gnome-terminal"):
        return subprocess.Popen([
            "gnome-terminal",
            f"--title={title}",
            "--working-directory",
            working_dir,
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
        ], cwd=working_dir)

    if which("xterm"):
        return subprocess.Popen([
            "xterm",
            "-T",
            title,
            "-e",
            "bash",
            "-lc",
            full_cmd,
        ], cwd=working_dir)

    return None


def open_process_in_new_terminal_windows(args: list[str]) -> Optional[subprocess.Popen]:
    ps_exe = get_powershell_exe()
    if not ps_exe:
        return None

    cmd = [ps_exe, "-NoExit", "-ExecutionPolicy", "Bypass", *args]
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    return subprocess.Popen(cmd, cwd=str(APP_DIR), creationflags=creationflags)


def start_terminal_process(
    *,
    title: str,
    command: str,
    pid_file: Path,
    display_name: str,
    windows_args: list[str],
    cwd: Optional[Path] = None,
) -> None:
    running, pid = process_status(pid_file)
    if running:
        print(f"{display_name} уже запущен (PID {pid}).")
        return

    if IS_WINDOWS:
        proc = open_process_in_new_terminal_windows(windows_args)
        if proc is None:
            print("Не найден PowerShell (pwsh/powershell) для запуска нового окна.")
            return
        write_pid_file(pid_file, proc.pid)
        print(f"{display_name} запущен (PID {proc.pid}).")
        return

    proc = open_process_in_new_terminal_linux(
        title=title,
        command=command,
        pid_file=pid_file,
        cwd=cwd,
    )
    if proc is None:
        print("Не найден терминал для запуска нового окна (gnome-terminal/x-terminal-emulator/xterm)")
        return

    real_pid = wait_for_pid_file(pid_file, timeout=5.0)
    if real_pid is None:
        print(f"Не удалось получить PID процесса: {display_name}.")
        return

    print(f"{display_name} запущен (PID {real_pid}).")