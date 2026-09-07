from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from nflfantasy.intelligence import analyze_news
from nflfantasy.news import NewsArticle


class IntelligenceTests(unittest.TestCase):
    def test_structured_analysis_is_validated_and_cached(self) -> None:
        article = NewsArticle("NFL", "Player One limited at practice", "Questionable", "https://example.com", datetime.now(UTC), ("Player One",), ("practice", "questionable"))
        raw = json.dumps([{"player_name": "Player One", "status": "uncertain", "start_likelihood": 0.65, "confidence": 0.8, "action": "monitor", "injury_summary": "Limited practice.", "explanation": "Participation is unresolved.", "evidence_titles": [article.title]}])
        calls = 0

        def generate(*args: object) -> str:
            nonlocal calls
            calls += 1
            return raw

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "analysis.json"
            first = analyze_news(["Player One"], [article], api_key="test", model="gemini-test", cache_file=cache, generate=generate)
            second = analyze_news(["Player One"], [article], api_key="test", model="gemini-test", cache_file=cache, generate=generate)

        self.assertEqual(first.insights[0].start_likelihood, 0.65)
        self.assertEqual(second.insights, first.insights)
        self.assertEqual(calls, 1)

    def test_unknown_player_is_rejected(self) -> None:
        article = NewsArticle("NFL", "Player One injury", "Out", "https://example.com", datetime.now(UTC), ("Player One",), ("injury",))
        raw = json.dumps([{"player_name": "Other", "status": "out", "start_likelihood": 0, "confidence": 1, "action": "sit", "injury_summary": "Out.", "explanation": "Ruled out.", "evidence_titles": [article.title]}])
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "unknown"):
            analyze_news(["Player One"], [article], api_key="test", model="gemini-test", cache_file=Path(directory) / "analysis.json", generate=lambda *args: raw)

    def test_daily_budget_is_checked_before_generation(self) -> None:
        article = NewsArticle("NFL", "Player One injury", "Out", "https://example.com", datetime.now(UTC), ("Player One",), ("injury",))
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(RuntimeError, "budget"):
            analyze_news(
                ["Player One"],
                [article],
                api_key="test",
                model="gemini-test",
                cache_file=Path(directory) / "analysis.json",
                budget_file=Path(directory) / "budget.json",
                daily_request_limit=0,
                generate=lambda *args: self.fail("Generator should not run"),
            )

    def test_evidence_must_belong_to_player(self) -> None:
        article = NewsArticle("NFL", "Player Two injury", "Out", "https://example.com", datetime.now(UTC), ("Player Two",), ("injury",))
        raw = json.dumps([{"player_name": "Player One", "status": "out", "start_likelihood": 0, "confidence": 1, "action": "sit", "injury_summary": "Out.", "explanation": "Ruled out.", "evidence_titles": [article.title]}])
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "evidence_titles"):
            analyze_news(["Player One", "Player Two"], [article], api_key="test", model="gemini-test", cache_file=Path(directory) / "analysis.json", generate=lambda *args: raw)


if __name__ == "__main__":
    unittest.main()