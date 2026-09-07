from __future__ import annotations

import unittest

from nflfantasy.lineup import recommend_lineup
from nflfantasy.recommendations import LeagueRules, Player


class LineupTests(unittest.TestCase):
    def test_highest_projected_eligible_players_start(self) -> None:
        roster = [
            Player(1, "QB", "QB", "BUF", 350),
            Player(2, "RB One", "RB", "DET", 300),
            Player(3, "RB Two", "RB", "ATL", 280),
            Player(4, "RB Flex", "RB", "IND", 260),
            Player(5, "RB Bench", "RB", "MIA", 200),
            Player(6, "WR One", "WR", "LAR", 290),
            Player(7, "WR Two", "WR", "CIN", 270),
            Player(8, "WR Bench", "WR", "DAL", 220),
            Player(9, "TE", "TE", "ARI", 240),
            Player(10, "K", "K", "BAL", 140),
            Player(11, "Defense", "D/ST", "DEN", 130),
        ]

        result = recommend_lineup(roster, LeagueRules())

        self.assertIn(("FLEX", "RB Flex"), {(item.slot, item.player.name) for item in result.starters})
        self.assertEqual([player.name for player in result.bench], ["WR Bench", "RB Bench"])
        self.assertEqual(result.expected_points, 2260)

    def test_missing_projections_are_reported(self) -> None:
        player = Player(1, "Unknown", "QB", "FA", 0)
        result = recommend_lineup([player], LeagueRules())
        self.assertEqual(result.missing_projections, (player,))


if __name__ == "__main__":
    unittest.main()