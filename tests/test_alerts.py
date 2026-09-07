from __future__ import annotations

import unittest
from datetime import UTC, datetime

from nflfantasy.alerts import build_alert
from nflfantasy.config import Config
from nflfantasy.intelligence import IntelligenceReport, PlayerInsight
from nflfantasy.news import NewsArticle
from nflfantasy.projections import WeeklyProjection
from nflfantasy.recommendations import LeagueRules, Player


class AlertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config(2026, "head_to_head", "snake", 0, 0, LeagueRules(teams=14))
        self.players = [
            Player(1, "Quarterback", "QB", "BUF", 350, adp=20),
            Player(2, "Running Back", "RB", "DET", 300, adp=2),
            Player(3, "Receiver", "WR", "LAR", 0, adp=8),
            Player(4, "Other Receiver", "WR", "MIN", 250, adp=25),
        ]

    def test_roster_alert_contains_schedule_and_missing_projection(self) -> None:
        text = build_alert(self.config, self.players, [], [1, 2, 3])
        self.assertIn("Thursday at 2:00 PM", text)
        self.assertIn("RECOMMENDED STARTERS", text)
        self.assertIn("N/A expected weekly points", text)
        self.assertIn("expected-points baseline is unavailable for: Receiver", text)

    def test_pre_draft_alert_contains_board(self) -> None:
        text = build_alert(self.config, self.players, [], [])
        self.assertIn("DRAFT BOARD", text)
        self.assertIn("No post-draft roster is configured", text)

    def test_intelligence_adds_evidence_and_deterministic_replacement(self) -> None:
        title = "Receiver questionable after limited practice"
        report = IntelligenceReport(
            datetime.now(UTC).isoformat(),
            "test",
            "hash",
            (PlayerInsight("Receiver", "uncertain", 0.4, 0.8, "sit", "Limited.", "Status unresolved.", (title,)),),
        )
        article = NewsArticle("NFL", title, "Questionable", "https://example.com/news", datetime.now(UTC), ("Receiver",), ("questionable",))
        text = build_alert(self.config, self.players, [], [3], report, [article])
        self.assertIn("start likelihood 40%", text)
        self.assertIn("Suggested replacement:", text)
        self.assertIn("https://example.com/news", text)

    def test_high_confidence_unavailable_player_is_withheld(self) -> None:
        players = [
            player if player.player_id != 3 else Player(3, "Receiver", "WR", "LAR", 300, adp=8)
            for player in self.players
        ] + [
            Player(5, "Third Receiver", "WR", "SEA", 200, adp=40),
            Player(6, "Bench Receiver", "WR", "GB", 150, adp=60),
        ]
        report = IntelligenceReport(
            datetime.now(UTC).isoformat(),
            "test",
            "hash",
            (PlayerInsight("Receiver", "out", 0.0, 0.95, "sit", "Ruled out.", "Will not play.", ("Receiver ruled out",)),),
        )
        article = NewsArticle("NFL", "Receiver ruled out", "Inactive", "https://example.com/out", datetime.now(UTC), ("Receiver",), ("out",))
        text = build_alert(self.config, players, [], [3, 4, 5, 6], report, [article])
        starter_lines = text.split("Expected starter weekly total:", 1)[0]
        self.assertNotIn("WR   Receiver ", starter_lines)
        self.assertIn("Withheld for strong availability risk: Receiver", text)
        self.assertIn("Suggested replacement: Bench Receiver", text)

    def test_intelligence_failure_keeps_espn_advice(self) -> None:
        text = build_alert(
            self.config,
            self.players,
            [],
            [1, 2],
            intelligence_warning="Gemini API unavailable.",
        )
        self.assertIn("RECOMMENDED STARTERS", text)
        self.assertIn("ESPN-only recommendations remain in effect", text)

    def test_weekly_projection_shows_opponent_venue_and_fixture_adjustment(self) -> None:
        weekly = {
            1: WeeklyProjection(1, "MIA", True, 22.5, 20.6, 1.9),
            2: WeeklyProjection(2, "GB", False, 15.2, 17.6, -2.4),
        }
        text = build_alert(
            self.config,
            self.players,
            [],
            [1, 2],
            weekly_projections=weekly,
        )
        self.assertIn("WEEKLY EXPECTED POINTS BY FIXTURE", text)
        self.assertIn("22.5 points vs MIA", text)
        self.assertIn("15.2 points at GB", text)
        self.assertIn("fixture +1.9", text)


if __name__ == "__main__":
    unittest.main()