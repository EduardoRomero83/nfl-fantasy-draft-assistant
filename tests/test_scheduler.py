from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nflfantasy.scheduler import TASK_NAME, install_windows_task, task_action


class SchedulerTests(unittest.TestCase):
    def test_task_action_uses_project_watchdog(self) -> None:
        action = task_action(Path("C:/NFL Fantasy"))
        self.assertIn("schedule-watchdog.ps1", action)
        self.assertIn('-ProjectRoot "C:\\NFL Fantasy"', action)

    def test_install_uses_thursday_at_two_pm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "schedule-watchdog.ps1").touch()
            python = root / ".venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
            with patch("nflfantasy.scheduler._run") as run:
                message = install_windows_task(root)

        task_command = run.call_args_list[1].args[0]
        self.assertIn(TASK_NAME, task_command)
        self.assertEqual(task_command[task_command.index("/D") + 1], "THU")
        self.assertEqual(task_command[task_command.index("/ST") + 1], "14:00")
        self.assertIn("Thursday at 2:00 PM", message)
        self.assertIn("StartWhenAvailable", run.call_args_list[2].args[0][-1])


if __name__ == "__main__":
    unittest.main()