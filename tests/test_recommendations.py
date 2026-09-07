from __future__ import annotations

import unittest

from nflfantasy.recommendations import (
    DraftPick,
    LeagueRules,
    Player,
    next_pick_for_position,
    recommend_players,
)


class RecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = LeagueRules(teams=2)
        self.players = [
            Player(1, "Elite RB", "RB", "A", 300, adp=1),
            Player(2, "Second RB", "RB", "B", 250, adp=3),
            Player(3, "Replacement RB", "RB", "C", 180, adp=8),
            Player(4, "Elite WR", "WR", "D", 290, adp=2),
            Player(5, "Second WR", "WR", "E", 245, adp=4),
            Player(6, "Replacement WR", "WR", "F", 175, adp=9),
            Player(7, "QB One", "QB", "G", 320, adp=5),
            Player(8, "QB Two", "QB", "H", 280, adp=10),
            Player(9, "TE One", "TE", "I", 210, adp=6),
            Player(10, "TE Two", "TE", "J", 150, adp=12),
        ]

    def test_drafted_players_are_removed(self) -> None:
        recommendations = recommend_players(
            self.players,
            [DraftPick(1, 1)],
            self.rules,
        )
        self.assertNotIn(1, {item.player.player_id for item in recommendations})

    def test_roster_need_changes_live_board(self) -> None:
        empty = recommend_players(self.players, [], self.rules)
        after_two_running_backs = recommend_players(
            self.players,
            [DraftPick(1, 1, is_mine=True), DraftPick(2, 2, is_mine=True)],
            self.rules,
        )
        empty_rb = next(item for item in empty if item.player.player_id == 2)
        filled_rb = next(item for item in after_two_running_backs if item.player.player_id == 3)
        self.assertGreater(empty_rb.need_multiplier, filled_rb.need_multiplier)

    def test_adp_fallback_works_when_projections_are_missing(self) -> None:
        players = [
            Player(index, f"RB {index}", "RB", "A", 0, adp=float(index))
            for index in range(1, 10)
        ] + [
            Player(100 + index, f"WR {index}", "WR", "B", 0, adp=float(index + 1))
            for index in range(1, 10)
        ]
        recommendations = recommend_players(players, [], self.rules)
        self.assertTrue(recommendations)
        self.assertIn("consensus value", recommendations[0].reason)
        self.assertGreater(recommendations[0].value_over_replacement, 0)

    def test_snake_order_finds_next_pick(self) -> None:
        self.assertEqual(next_pick_for_position(0, 12, 4), 4)
        self.assertEqual(next_pick_for_position(4, 12, 4), 21)
        self.assertEqual(next_pick_for_position(21, 12, 4), 28)
        self.assertIsNone(next_pick_for_position(0, 12, 0))


if __name__ == "__main__":
    unittest.main()