from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


RISK_TERMS = frozenset(
    {
        "active",
        "cleared",
        "concussion",
        "doubtful",
        "expected to play",
        "full practice",
        "game-time decision",
        "inactive",
        "injured",
        "injury",
        "limited practice",
        "likely to play",
        "out",
        "practice",
        "questionable",
        "return",
        "ruled out",
        "start",
        "suspended",
        "suspension",
    }
)
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class NewsArticle:
    source_name: str
    title: str
    summary: str
    url: str
    published_at: datetime
    entities: tuple[str, ...]
    risks: tuple[str, ...]


def _plain_text(value: str) -> str:
    return " ".join(html.unescape(TAG_PATTERN.sub(" ", value)).split())


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(phrase)}(?![\w])", text, re.IGNORECASE) is not None


def parse_rss(payload: bytes, entities: list[str], max_age_days: int = 7) -> list[NewsArticle]:
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    root = ET.fromstring(payload)
    articles: list[NewsArticle] = []
    for item in root.findall("./channel/item"):
        title = _plain_text(item.findtext("title", default=""))
        summary = _plain_text(item.findtext("description", default=""))
        url = item.findtext("link", default="").strip()
        published_text = item.findtext("pubDate", default="")
        source = item.find("source")
        if not title or not url or not published_text:
            continue
        published_at = parsedate_to_datetime(published_text)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)
        published_at = published_at.astimezone(UTC)
        if published_at < cutoff:
            continue
        text = f"{title} {summary}"
        matched_entities = tuple(entity for entity in entities if _contains(text, entity))
        matched_risks = tuple(sorted(term for term in RISK_TERMS if _contains(text, term)))
        if matched_entities and matched_risks:
            articles.append(
                NewsArticle(
                    source_name=_plain_text(source.text or "") if source is not None else "Google News",
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=published_at,
                    entities=matched_entities,
                    risks=matched_risks,
                )
            )
    return articles


def build_news_urls(entities: list[str], max_queries: int = 4) -> list[str]:
    urls: list[str] = []
    risk_query = '(injury OR questionable OR doubtful OR out OR practice OR "expected to play" OR suspension)'
    for start in range(0, len(entities), 5):
        names = entities[start : start + 5]
        if not names:
            continue
        player_query = " OR ".join(f'"{name}"' for name in names)
        query = f"({player_query}) {risk_query} NFL fantasy when:7d"
        urls.append(
            "https://news.google.com/rss/search?"
            + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        )
        if len(urls) >= max_queries:
            break
    return urls


def fetch_news(entities: list[str], max_queries: int = 4) -> list[NewsArticle]:
    articles: dict[str, NewsArticle] = {}
    for url in build_news_urls(entities, max_queries):
        request = urllib.request.Request(url, headers={"User-Agent": "NFLFantasyDraftAssistant/0.1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            try:
                parsed = parse_rss(response.read(), entities)
            except ET.ParseError as error:
                raise RuntimeError("Google News returned malformed RSS.") from error
            for article in parsed:
                articles.setdefault(article.url, article)
    return sorted(articles.values(), key=lambda article: article.published_at, reverse=True)