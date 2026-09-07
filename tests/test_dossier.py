from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nflfantasy.config import Config
from nflfantasy.dossier import write_dossier
from nflfantasy.recommendations import DraftPick, LeagueRules, Player, recommend_players


class DossierTests(unittest.TestCase):
    def test_dossier_contains_live_context_and_prompt(self) -> None:
        players = [
            Player(1, "Player One", "RB", "BUF", 250, adp=4),
            Player(2, "Player Two", "WR", "PHI", 240, adp=7),
        ]
        picks = [DraftPick(1, 1, is_mine=True)]
        config = Config(2026, "head_to_head", "snake", 0, 0, LeagueRules(teams=10))
        recommendations = recommend_players(players, picks, config.rules)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "context.md"
            write_dossier(output, config, players, picks, recommendations, source="test", source_updated_at="now")
            content = output.read_text(encoding="utf-8")
        self.assertIn("Player One (RB)", content)
        self.assertIn("best pick now and three fallbacks", content)
        self.assertIn("Player Two", content)


if __name__ == "__main__":
    unittest.main()