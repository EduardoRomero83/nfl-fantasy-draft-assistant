from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nflfantasy.config import EmailConfig
from nflfantasy.email_report import send_email_report


class EmailReportTests(unittest.TestCase):
    def test_email_is_sent_through_outlook_with_attachment(self) -> None:
        settings = EmailConfig("to@example.com", "Board")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("# Draft board", encoding="utf-8")
            with patch("nflfantasy.email_report.subprocess.run") as run:
                run.return_value.returncode = 0
                run.return_value.stderr = ""
                run.return_value.stdout = ""
                send_email_report(report, settings)

        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(payload["sender"], "to@example.com")
        self.assertEqual(payload["recipient"], "to@example.com")
        self.assertEqual(payload["attachment"], str(report.resolve()))
        self.assertIn("Outlook.Application", run.call_args.args[0][-1])
        self.assertIn("SendUsingAccount", run.call_args.args[0][-1])
        self.assertIn("SmtpAddress", run.call_args.args[0][-1])

    def test_outlook_timeout_is_reported(self) -> None:
        settings = EmailConfig("to@example.com", "Board")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("# Draft board", encoding="utf-8")
            with patch(
                "nflfantasy.email_report.subprocess.run",
                side_effect=subprocess.TimeoutExpired("powershell", 60),
            ):
                with self.assertRaisesRegex(RuntimeError, "within 60 seconds"):
                    send_email_report(report, settings)

    def test_missing_matching_outlook_account_is_reported(self) -> None:
        settings = EmailConfig("to@example.com", "Board")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("# Draft board", encoding="utf-8")
            with patch("nflfantasy.email_report.subprocess.run") as run:
                run.return_value.returncode = 1
                run.return_value.stderr = (
                    "Classic Outlook has no signed-in account matching to@example.com."
                )
                run.return_value.stdout = ""
                with self.assertRaisesRegex(RuntimeError, "no signed-in account"):
                    send_email_report(report, settings)


if __name__ == "__main__":
    unittest.main()