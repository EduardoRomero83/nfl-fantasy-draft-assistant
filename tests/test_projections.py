from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from nflfantasy.projections import Game, fixture_multiplier, project_week, regular_season_complete
from nflfantasy.recommendations import Player


class ProjectionTests(unittest.TestCase):
    def test_strong_opponent_and_venue_affect_projection(self) -> None:
        strong_defense = fixture_multiplier("WR", (1.0, 1.5), True)
        average_away = fixture_multiplier("WR", (1.0, 1.0), False)
        self.assertLess(strong_defense, 1.0)
        self.assertAlmostEqual(average_away, 0.97)

    def test_fixture_multiplier_is_bounded(self) -> None:
        self.assertEqual(fixture_multiplier("WR", (1.0, 10.0), False), 0.78)
        self.assertEqual(fixture_multiplier("WR", (1.0, 0.01), True), 1.18)

    def test_defense_uses_opponent_attack_strength(self) -> None:
        weak_attack = fixture_multiplier("D/ST", (0.6, 1.8), True)
        strong_attack = fixture_multiplier("D/ST", (1.8, 0.6), True)
        self.assertGreater(weak_attack, strong_attack)

    def test_project_week_uses_opponent_and_home_status(self) -> None:
        now = datetime(2026, 9, 7, tzinfo=UTC)
        historical = [
            Game("old", 2025, 2, 1, now - timedelta(days=365), "BUF", "NYJ", True, 35, 10),
            Game("old2", 2025, 2, 2, now - timedelta(days=358), "NE", "NYJ", True, 28, 7),
        ]
        upcoming = Game("new", 2026, 2, 1, now + timedelta(days=3), "BUF", "NYJ", False)
        players = [Player(1, "Home WR", "WR", "BUF", 170), Player(2, "Away WR", "WR", "NYJ", 170)]
        projections = project_week(players, [*historical, upcoming], now)
        self.assertEqual(projections[1].opponent, "NYJ")
        self.assertTrue(projections[1].is_home)
        self.assertGreater(projections[1].expected_points, projections[2].expected_points)

    def test_regular_season_complete_requires_full_schedule(self) -> None:
        now = datetime(2027, 1, 10, tzinfo=UTC)
        complete = [
            Game(str(index), 2026, 2, index // 16 + 1, now, "BUF", "NYJ", True, 21, 17)
            for index in range(270)
        ]
        self.assertTrue(regular_season_complete(complete, 2026))
        self.assertFalse(regular_season_complete(complete[:269], 2026))
        self.assertFalse(
            regular_season_complete([*complete[:-1], Game("future", 2026, 2, 18, now, "BUF", "NYJ", False)], 2026)
        )


if __name__ == "__main__":
    unittest.main()