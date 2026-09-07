from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nflfantasy.cli import _print_board, _run_draft_room
from nflfantasy.config import Config, GeminiConfig
from nflfantasy.intelligence import DraftReview
from nflfantasy.paths import AppPaths
from nflfantasy.recommendations import LeagueRules, Player
from nflfantasy.storage import load_picks


class DraftRoomTests(unittest.TestCase):
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

    def _players(self, count: int = 8) -> list[Player]:
        return [
            Player(
                index,
                f"Player {index}",
                "WR" if index % 2 else "RB",
                "NFL",
                0,
                float(index),
            )
            for index in range(1, count + 1)
        ]

    def _config(self, *, gemini: bool = False) -> Config:
        return Config(
            season=2026,
            matchup="head_to_head",
            draft_type="snake",
            my_team=0,
            draft_position=1,
            rules=LeagueRules(teams=2),
            gemini=GeminiConfig(enabled=gemini),
        )

    def test_number_records_pick_and_marks_my_snake_slot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            prompts = []
            answers = iter(["1", "quit"])

            def answer(prompt: str) -> str:
                prompts.append(prompt)
                return next(answers)

            with patch("builtins.input", side_effect=answer), patch(
                "nflfantasy.cli._print_board"
            ), patch("nflfantasy.cli._write_current_dossier"):
                _run_draft_room(paths, self._config(), self._players(), [])

            picks = load_picks(paths.draft_file)

        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0].player_id, 1)
        self.assertTrue(picks[0].is_mine)
        self.assertIn("Actual player selected at overall pick #1", prompts[0])

    def test_board_labels_every_numeric_metric(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _print_board(self._players(), [], self._config(), 1)

        board = output.getvalue()
        self.assertIn("Next overall selection: #1", board)
        self.assertIn("ESPN season projection:", board)
        self.assertIn("Value over replacement:", board)
        self.assertIn("ESPN average draft position:", board)
        self.assertIn("Roster-need multiplier:", board)
        self.assertIn("Estimated availability:", board)

    def test_unknown_name_returns_to_pick_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            with patch("builtins.input", side_effect=["Not A Player", "quit"]), patch(
                "nflfantasy.cli._print_board"
            ), patch("nflfantasy.cli._write_current_dossier"), patch(
                "builtins.print"
            ) as output:
                _run_draft_room(paths, self._config(), self._players(), [])

        self.assertFalse(paths.draft_file.exists())
        self.assertTrue(
            any(
                "No player matches" in str(call.args[0])
                for call in output.call_args_list
                if call.args
            )
        )

    def test_gemini_reviews_each_completed_round(self) -> None:
        review = DraftReview(
            generated_at="now",
            model="gemini-test",
            input_hash="hash",
            round_number=1,
            primary_pick="Player 3",
            fallback_picks=("Player 4", "Player 5", "Player 6"),
            roster_assessment="Balanced.",
            strategy_adjustment="Stay flexible.",
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            with patch("builtins.input", side_effect=["1", "1", "quit"]), patch(
                "nflfantasy.cli._print_board"
            ), patch("nflfantasy.cli._write_current_dossier"), patch(
                "nflfantasy.cli.load_api_key", return_value="key"
            ), patch(
                "nflfantasy.cli.analyze_draft_round", return_value=review
            ) as analyze:
                _run_draft_room(
                    paths,
                    self._config(gemini=True),
                    self._players(),
                    [],
                )

        analyze.assert_called_once()


if __name__ == "__main__":
    unittest.main()
