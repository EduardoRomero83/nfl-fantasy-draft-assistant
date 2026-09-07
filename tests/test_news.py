from __future__ import annotations

import unittest
from datetime import UTC, datetime
from unittest.mock import patch
import xml.etree.ElementTree as ET

from nflfantasy.news import build_news_urls, fetch_news, parse_rss


class NewsTests(unittest.TestCase):
    def test_parse_rss_requires_player_and_risk(self) -> None:
        published = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        payload = f"""<rss><channel>
        <item><title>Player One limited at practice</title><link>https://example.com/one</link><pubDate>{published}</pubDate><description>Questionable</description></item>
        <item><title>Player Two signs shoes</title><link>https://example.com/two</link><pubDate>{published}</pubDate><description>Fashion</description></item>
        </channel></rss>""".encode()
        articles = parse_rss(payload, ["Player One", "Player Two"])
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].entities, ("Player One",))

    def test_queries_are_bounded(self) -> None:
        urls = build_news_urls([f"Player {index}" for index in range(30)], max_queries=4)
        self.assertEqual(len(urls), 4)
        self.assertTrue(all("news.google.com" in url for url in urls))

    @patch("nflfantasy.news.urllib.request.urlopen")
    def test_malformed_rss_becomes_fallback_safe_error(self, urlopen: object) -> None:
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"<rss>"
        with self.assertRaisesRegex(RuntimeError, "malformed RSS"):
            fetch_news(["Player One"])


if __name__ == "__main__":
    unittest.main()