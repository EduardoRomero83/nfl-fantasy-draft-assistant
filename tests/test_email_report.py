from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nflfantasy.config import EmailConfig
from nflfantasy.email_report import send_email_report


class EmailReportTests(unittest.TestCase):
    def test_email_is_sent_only_with_explicit_credentials(self) -> None:
        settings = EmailConfig("smtp.example.com", 587, True, "from@example.com", "to@example.com", "Board")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("# Draft board", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"NFLFANTASY_SMTP_USERNAME": "user", "NFLFANTASY_SMTP_PASSWORD": "secret"},
                clear=False,
            ), patch("nflfantasy.email_report.smtplib.SMTP") as smtp:
                send_email_report(report, settings)

        client = smtp.return_value.__enter__.return_value
        client.starttls.assert_called_once_with()
        client.login.assert_called_once_with("user", "secret")
        client.send_message.assert_called_once()

    def test_missing_credentials_are_rejected(self) -> None:
        settings = EmailConfig("smtp.example.com", 587, True, "from@example.com", "to@example.com", "Board")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            report = Path(directory) / "report.md"
            report.write_text("# Draft board", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SETUP.cmd"):
                send_email_report(report, settings)


if __name__ == "__main__":
    unittest.main()