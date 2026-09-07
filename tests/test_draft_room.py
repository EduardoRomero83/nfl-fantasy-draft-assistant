from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from nflfantasy.cli import (
    _configure_draft_position,
    _find_player,
    _print_board,
    _run_draft_room,
)
from nflfantasy.config import Config, GeminiConfig, ensure_config, load_config
from nflfantasy.intelligence import DraftReview
from nflfantasy.paths import AppPaths
from nflfantasy.recommendations import DraftPick, LeagueRules, Player
from nflfantasy.storage import load_picks, load_roster, save_picks, save_roster


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
        self.assertEqual(picks[0].fantasy_team, 1)
        self.assertIn("Overall pick #1 - draft slot 1 [YOUR PICK]", prompts[0])

    def test_launch_updates_position_and_reclassifies_existing_picks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            ensure_config(paths.config_file)
            config = load_config(paths.config_file)
            picks = [
                DraftPick(1, 1, 1, True),
                DraftPick(2, 2, 2, False),
            ]
            save_picks(paths.draft_file, picks)

            with patch("builtins.input", return_value="2"):
                updated = _configure_draft_position(paths, config, picks)

            saved = load_picks(paths.draft_file)

        self.assertEqual(updated.draft_position, 2)
        self.assertEqual([pick.fantasy_team for pick in saved], [1, 2])
        self.assertEqual([pick.is_mine for pick in saved], [False, True])

    def test_launch_reprompts_for_invalid_position(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            ensure_config(paths.config_file)
            config = load_config(paths.config_file)
            with patch("builtins.input", side_effect=["0", "3"]) as prompt:
                updated = _configure_draft_position(paths, config, [])

        self.assertEqual(updated.draft_position, 3)
        self.assertEqual(prompt.call_count, 2)

    def test_player_name_variations_resolve_without_gemini(self) -> None:
        players = [
            Player(1, "Drake London", "WR", "ATL", 0, 10),
            Player(2, "Justin Jefferson", "WR", "MIN", 0, 2),
        ]

        for query in ("DRAKE London", "d.london", "London, Drake", "Drake Londn"):
            with self.subTest(query=query):
                self.assertEqual(_find_player(players, query).player_id, 1)

    def test_ambiguous_surname_is_rejected(self) -> None:
        players = [
            Player(1, "A.J. Brown", "WR", "PHI", 0, 10),
            Player(2, "Marquise Brown", "WR", "KC", 0, 80),
        ]

        with self.assertRaisesRegex(ValueError, "ambiguous"):
            _find_player(players, "Brown")

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

    def test_confirmed_reset_clears_only_draft_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            picks = [DraftPick(1, 1, 1, True)]
            save_picks(paths.draft_file, picks)
            save_roster(paths.roster_file, [1])
            paths.config_file.write_text("settings", encoding="utf-8")
            paths.secrets_file.write_text("GEMINI_API_KEY=secret", encoding="utf-8")
            paths.players_file.write_text("players", encoding="utf-8")
            review = paths.data_dir / "latest-draft-review.json"
            budget = paths.data_dir / "draft-ai-budget.json"
            review.write_text("review", encoding="utf-8")
            budget.write_text("budget", encoding="utf-8")

            with patch(
                "builtins.input", side_effect=["reset", "RESET", "quit"]
            ), patch("nflfantasy.cli._print_board"), patch(
                "nflfantasy.cli._write_current_dossier"
            ):
                _run_draft_room(paths, self._config(), self._players(), picks)

            remaining_picks = load_picks(paths.draft_file)
            remaining_roster = load_roster(paths.roster_file)
            kept_files = [
                paths.config_file.exists(),
                paths.secrets_file.exists(),
                paths.players_file.exists(),
            ]
            removed_files = [review.exists(), budget.exists()]

        self.assertEqual(remaining_picks, [])
        self.assertEqual(remaining_roster, [])
        self.assertEqual(kept_files, [True, True, True])
        self.assertEqual(removed_files, [False, False])

    def test_unconfirmed_reset_keeps_draft(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._paths(Path(directory))
            picks = [DraftPick(1, 1, 1, True)]
            save_picks(paths.draft_file, picks)
            with patch(
                "builtins.input", side_effect=["reset", "no", "quit"]
            ), patch("nflfantasy.cli._print_board"), patch(
                "nflfantasy.cli._write_current_dossier"
            ):
                _run_draft_room(paths, self._config(), self._players(), picks)

            remaining_picks = load_picks(paths.draft_file)

        self.assertEqual(len(remaining_picks), 1)

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
            draft_slots = [
                pick.fantasy_team for pick in load_picks(paths.draft_file)
            ]

        analyze.assert_called_once()
        self.assertEqual(draft_slots, [1, 2])


if __name__ == "__main__":
    unittest.main()
