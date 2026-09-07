from __future__ import annotations

import unittest

from nflfantasy.alerts import build_alert
from nflfantasy.config import Config
from nflfantasy.recommendations import LeagueRules, Player


class AlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(2026, "head_to_head", "snake", 0, 0, LeagueRules(teams=14))
        self.players = [
            Player(1, "Quarterback", "QB", "BUF", 350, adp=20),
            Player(2, "Running Back", "RB", "DET", 300, adp=2),
            Player(3, "Receiver", "WR", "LAR", 0, adp=8),
        ]

    def test_roster_alert_contains_schedule_and_missing_projection(self) -> None:
        text = build_alert(self.config, self.players, [], [1, 2, 3])
        self.assertIn("Thursday at 2:00 PM", text)
        self.assertIn("RECOMMENDED STARTERS", text)
        self.assertIn("N/A expected season points", text)
        self.assertIn("ESPN has not published trustworthy projections for: Receiver", text)

    def test_pre_draft_alert_contains_board(self) -> None:
        text = build_alert(self.config, self.players, [], [])
        self.assertIn("DRAFT BOARD", text)
        self.assertIn("No post-draft roster is configured", text)


if __name__ == "__main__":
    unittest.main()