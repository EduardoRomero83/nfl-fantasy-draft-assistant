from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nflfantasy.paths import AppPaths
from nflfantasy.setup_wizard import run_setup_wizard


class SetupWizardTests(unittest.TestCase):
    def _paths(self, data: Path) -> AppPaths:
        return AppPaths(
            data,
            data / "config.toml",
            data / "secrets.env",
            data / "players.json",
            data / "draft.json",
            data / "roster.json",
            data / "dossier.md",
            data / "alert.txt",
            data / "intelligence.json",
            data / "budget.json",
            data / "logs",
        )

    def test_setup_prompts_for_and_privately_stores_gemini_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            paths = self._paths(data)
            answers = iter(["", "", "", "", "n", "y"])
            with patch("builtins.input", side_effect=lambda prompt: next(answers)), patch(
                "nflfantasy.setup_wizard.getpass.getpass", return_value="shared-api-key"
            ) as getpass:
                run_setup_wizard(paths)

            config = paths.config_file.read_text(encoding="utf-8")
            secrets = paths.secrets_file.read_text(encoding="utf-8")

        self.assertIn("same key used by UCL", getpass.call_args.args[0])
        self.assertIn("enabled = true", config)
        self.assertNotIn("shared-api-key", config)
        self.assertIn("GEMINI_API_KEY=shared-api-key", secrets)

    def test_email_setup_uses_outlook_without_requesting_a_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            paths.secrets_file.write_text(
                "NFLFANTASY_SMTP_USERNAME=old\n"
                "NFLFANTASY_SMTP_PASSWORD=old-password\n",
                encoding="utf-8",
            )
            answers = iter(["", "", "", "", "y", "owner@example.com", "n"])
            with patch("builtins.input", side_effect=lambda prompt: next(answers)), patch(
                "nflfantasy.setup_wizard.getpass.getpass"
            ) as getpass:
                run_setup_wizard(paths)

            config = paths.config_file.read_text(encoding="utf-8")
            secrets = paths.secrets_file.read_text(encoding="utf-8")

        getpass.assert_not_called()
        self.assertIn('recipient = "owner@example.com"', config)
        self.assertNotIn("smtp_", config)
        self.assertNotIn("SMTP", secrets)


if __name__ == "__main__":
    unittest.main()