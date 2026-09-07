from __future__ import annotations

import unittest

from nflfantasy.espn import parse_players


class EspnTests(unittest.TestCase):
    def test_parse_player_projection_and_adp(self) -> None:
        players = parse_players(
            [
                {
                    "id": 42,
                    "fullName": "Test Receiver",
                    "defaultPositionId": 3,
                    "proTeamId": 2,
                    "injuryStatus": "ACTIVE",
                    "ownership": {"averageDraftPosition": 12.5, "auctionValueAverage": 31},
                    "stats": [
                        {
                            "seasonId": 2026,
                            "scoringPeriodId": 0,
                            "statSourceId": 1,
                            "statSplitTypeId": 0,
                            "appliedTotal": 251.25,
                        }
                    ],
                    "rankings": {"0": {"overallRanking": 9}},
                }
            ]
        )
        self.assertEqual(players[0].position, "WR")
        self.assertEqual(players[0].pro_team, "BUF")
        self.assertEqual(players[0].projected_points, 251.25)
        self.assertEqual(players[0].adp, 12.5)
        self.assertEqual(players[0].source_rank, 9)

    def test_projection_ignores_other_seasons_and_weekly_splits(self) -> None:
        payload = [
            {
                "id": 42,
                "fullName": "Test Receiver",
                "defaultPositionId": 3,
                "stats": [
                    {"seasonId": 2025, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0, "appliedTotal": 300},
                    {"seasonId": 2026, "scoringPeriodId": 1, "statSourceId": 1, "statSplitTypeId": 1, "appliedTotal": 20},
                    {"seasonId": 2026, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0, "appliedTotal": 250},
                ],
            }
        ]

        self.assertEqual(parse_players(payload, 2026)[0].projected_points, 250)

    def test_implausible_projection_is_treated_as_unavailable(self) -> None:
        payload = [
            {
                "id": 42,
                "fullName": "Test Tight End",
                "defaultPositionId": 4,
                "stats": [
                    {"seasonId": 2026, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0, "appliedTotal": 2632}
                ],
            },
            {
                "id": 43,
                "fullName": "Test Kicker",
                "defaultPositionId": 5,
                "stats": [
                    {"seasonId": 2026, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0, "appliedTotal": -4800}
                ],
            },
        ]

        self.assertEqual([player.projected_points for player in parse_players(payload, 2026)], [0, 0])


if __name__ == "__main__":
    unittest.main()