from __future__ import annotations

import subprocess
from pathlib import Path


TASK_NAME = "NFL Fantasy Thursday Alert"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def watchdog_path(root: Path) -> Path:
    return root / "scripts" / "schedule-watchdog.ps1"


def task_action(root: Path) -> str:
    script = watchdog_path(root)
    return (
        f'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{script}" '
        f'-ProjectRoot "{root}"'
    )


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or error.stdout or "unknown error").strip()
        raise RuntimeError(f"Windows Task Scheduler failed: {details}") from error


def install_windows_task(root: Path | None = None) -> str:
    root = root or project_root()
    script = watchdog_path(root)
    python = root / ".venv" / "Scripts" / "python.exe"
    if not script.is_file():
        raise RuntimeError(f"Scheduler watchdog is missing: {script}")
    if not python.is_file():
        raise RuntimeError("The persistent Python environment is missing. Run SETUP.cmd first.")
    _run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-ProjectRoot",
            str(root),
            "-HealthCheckOnly",
        ]
    )
    _run(
        [
            "schtasks.exe",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            task_action(root),
            "/SC",
            "WEEKLY",
            "/D",
            "THU",
            "/ST",
            "14:00",
            "/RL",
            "LIMITED",
            "/F",
        ]
    )
    settings_script = (
        f"$task = Get-ScheduledTask -TaskName '{TASK_NAME}'; "
        "$task.Settings.DisallowStartIfOnBatteries = $false; "
        "$task.Settings.StopIfGoingOnBatteries = $false; "
        "$task.Settings.StartWhenAvailable = $true; "
        "$task.Settings.WakeToRun = $true; "
        "$task.Settings.ExecutionTimeLimit = 'PT30M'; "
        "$task.Settings.MultipleInstances = 'IgnoreNew'; "
        "$task.Settings.RestartCount = 3; "
        "$task.Settings.RestartInterval = 'PT5M'; "
        "Set-ScheduledTask -InputObject $task | Out-Null"
    )
    _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", settings_script])
    return f'Installed "{TASK_NAME}" for Thursday at 2:00 PM.'


def remove_windows_task() -> str:
    _run(["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"])
    return f'Removed "{TASK_NAME}".'


def task_status() -> str:
    result = _run(["schtasks.exe", "/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
    return result.stdout.strip()