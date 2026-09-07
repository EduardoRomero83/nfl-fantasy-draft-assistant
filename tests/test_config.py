from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nflfantasy.config import ensure_config, load_config, update_draft_position


class ConfigTests(unittest.TestCase):
    def test_default_config_matches_confirmed_league(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            ensure_config(path)
            config = load_config(path)

        self.assertEqual(config.rules.teams, 14)
        self.assertEqual(config.rules.scoring, "ppr")
        self.assertEqual(config.matchup, "head_to_head")
        self.assertEqual(config.draft_type, "snake")
        self.assertEqual(config.draft_position, 0)
        self.assertEqual(config.rules.slots()["BE"], 7)
        self.assertIsNone(config.email)
        self.assertFalse(config.gemini.enabled)
        self.assertEqual(config.gemini.max_queries, 4)

    def test_invalid_draft_position_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text("teams = 14\ndraft_position = 15\n[roster]\nQB = 1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "draft_position"):
                load_config(path)

    def test_draft_position_update_preserves_other_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            ensure_config(path)

            config = update_draft_position(path, 7)
            source = path.read_text(encoding="utf-8")

        self.assertEqual(config.draft_position, 7)
        self.assertIn("teams = 14", source)
        self.assertIn("[email]", source)
        self.assertIn("[gemini]", source)


if __name__ == "__main__":
    unittest.main()