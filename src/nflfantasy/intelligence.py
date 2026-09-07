from __future__ import annotations

import hashlib
import json
import msvcrt
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .news import NewsArticle
from .recommendations import DraftPick, LeagueRules, Player, Recommendation


ACTIONS = frozenset({"start", "sit", "monitor", "avoid", "target"})
STATUSES = frozenset({"healthy", "likely", "uncertain", "unlikely", "out"})


@dataclass(frozen=True)
class PlayerInsight:
    player_name: str
    status: str
    start_likelihood: float
    confidence: float
    action: str
    injury_summary: str
    explanation: str
    evidence_titles: tuple[str, ...]


@dataclass(frozen=True)
class IntelligenceReport:
    generated_at: str
    model: str
    input_hash: str
    insights: tuple[PlayerInsight, ...]


@dataclass(frozen=True)
class DraftReview:
    generated_at: str
    model: str
    input_hash: str
    round_number: int
    primary_pick: str
    fallback_picks: tuple[str, ...]
    roster_assessment: str
    strategy_adjustment: str


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _reserve_budget(path: Path, estimated_tokens: int, request_limit: int, token_limit: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        try:
            today = datetime.now(UTC).date().isoformat()
            payload: dict[str, object] = {}
            if path.is_file():
                payload = json.loads(path.read_text(encoding="utf-8"))
            requests = int(payload.get("requests", 0)) if payload.get("date") == today else 0
            tokens = int(payload.get("estimated_tokens", 0)) if payload.get("date") == today else 0
            if requests + 1 > request_limit or tokens + estimated_tokens > token_limit:
                raise RuntimeError("Gemini daily usage budget reached.")
            _atomic_json(
                path,
                {"date": today, "requests": requests + 1, "estimated_tokens": tokens + estimated_tokens},
            )
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def load_api_key(secrets_file: Path) -> str:
    if not secrets_file.is_file():
        return ""
    for line in secrets_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "GEMINI_API_KEY":
            return value.strip()
    return ""


def _prompt(entities: list[str], articles: list[NewsArticle]) -> str:
    evidence = [
        {
            "title": article.title,
            "summary": article.summary[:700],
            "source": article.source_name,
            "published_at": article.published_at.isoformat(),
            "entities": article.entities,
            "risks": article.risks,
        }
        for article in articles
    ]
    return (
        "Analyze NFL fantasy availability using only the supplied RSS evidence. "
        "Do not add uncited facts. Return one item only for players with relevant evidence. "
        "Use start_likelihood as a 0-1 estimate that the player will be active and start; "
        "confidence measures evidence quality. For draft or waiver candidates use target/avoid/monitor; "
        "for roster players start/sit/monitor is allowed. Explain uncertainty and cite exact supplied titles.\n"
        + json.dumps({"players": entities, "articles": evidence}, ensure_ascii=True)
    )


def _generate(api_key: str, model: str, prompt: str, max_output_tokens: int) -> str:
    safe_model = urllib.parse.quote(model, safe="-_.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent"
    properties = {
        "player_name": {"type": "string"},
        "status": {"type": "string", "enum": sorted(STATUSES)},
        "start_likelihood": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "action": {"type": "string", "enum": sorted(ACTIONS)},
        "injury_summary": {"type": "string"},
        "explanation": {"type": "string"},
        "evidence_titles": {"type": "array", "items": {"type": "string"}},
    }
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": properties,
                        "required": list(properties),
                        "additionalProperties": False,
                    },
                },
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.1,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Gemini API returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Gemini API connection failed: {error.reason}.") from error
    try:
        return str(payload["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini response did not contain generated text.") from error


def _validate(raw: str, entities: list[str], articles: list[NewsArticle]) -> tuple[PlayerInsight, ...]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("Gemini response must be a JSON array.")
    allowed_entities = set(entities)
    allowed_titles = {article.title for article in articles}
    insights: list[PlayerInsight] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Gemini response contains a non-object result.")
        player_name = str(item.get("player_name", ""))
        status = str(item.get("status", ""))
        action = str(item.get("action", ""))
        likelihood = item.get("start_likelihood")
        confidence = item.get("confidence")
        titles = item.get("evidence_titles")
        if player_name not in allowed_entities or player_name in seen:
            raise ValueError("Gemini response contains an unknown or duplicate player.")
        if status not in STATUSES or action not in ACTIONS:
            raise ValueError("Gemini response contains an invalid status or action.")
        if not isinstance(likelihood, (int, float)) or not 0 <= float(likelihood) <= 1:
            raise ValueError("Gemini start_likelihood must be between 0 and 1.")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise ValueError("Gemini confidence must be between 0 and 1.")
        player_titles = {
            article.title for article in articles if player_name in article.entities
        }
        if not isinstance(titles, list) or not titles or not set(titles).issubset(player_titles):
            raise ValueError("Gemini evidence_titles must cite supplied articles.")
        for field in ("injury_summary", "explanation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Gemini {field} must be nonempty text.")
        insights.append(
            PlayerInsight(
                player_name=player_name,
                status=status,
                start_likelihood=float(likelihood),
                confidence=float(confidence),
                action=action,
                injury_summary=item["injury_summary"].strip(),
                explanation=item["explanation"].strip(),
                evidence_titles=tuple(titles),
            )
        )
        seen.add(player_name)
    return tuple(insights)


def analyze_news(
    entities: list[str],
    articles: list[NewsArticle],
    *,
    api_key: str,
    model: str,
    cache_file: Path,
    budget_file: Path | None = None,
    max_articles: int = 12,
    max_output_tokens: int = 2500,
    daily_request_limit: int = 2,
    daily_token_limit: int = 20000,
    generate: object | None = None,
) -> IntelligenceReport:
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")
    selected = articles[:max_articles]
    prompt = _prompt(entities, selected)
    input_hash = hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()
    if cache_file.is_file():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        generated_at = datetime.fromisoformat(str(cached.get("generated_at", "")))
        if cached.get("input_hash") == input_hash and datetime.now(UTC) - generated_at < timedelta(hours=6):
            return IntelligenceReport(
                generated_at=cached["generated_at"],
                model=cached["model"],
                input_hash=input_hash,
                insights=tuple(
                    PlayerInsight(
                        **{**item, "evidence_titles": tuple(item["evidence_titles"])}
                    )
                    for item in cached.get("insights", [])
                ),
            )
    if budget_file is not None:
        _reserve_budget(
            budget_file,
            max(1, len(prompt.encode("utf-8")) // 4),
            daily_request_limit,
            daily_token_limit,
        )
    generator = generate or _generate
    raw = generator(api_key, model, prompt, max_output_tokens)
    report = IntelligenceReport(
        generated_at=datetime.now(UTC).isoformat(),
        model=model,
        input_hash=input_hash,
        insights=_validate(raw, entities, selected),
    )
    _atomic_json(
        cache_file,
        {**asdict(report), "insights": [asdict(item) for item in report.insights]},
    )
    return report


def _draft_prompt(
    round_number: int,
    players: list[Player],
    picks: list[DraftPick],
    recommendations: list[Recommendation],
    rules: LeagueRules,
) -> str:
    by_id = {player.player_id: player for player in players}
    my_roster = [
        by_id[pick.player_id]
        for pick in picks
        if pick.is_mine and pick.player_id in by_id
    ]
    round_start = max(0, len(picks) - rules.teams)
    recent_picks = [
        {
            "player": by_id[pick.player_id].name,
            "position": by_id[pick.player_id].position,
            "mine": pick.is_mine,
        }
        for pick in picks[round_start:]
        if pick.player_id in by_id
    ]
    board = [
        {
            "player": item.player.name,
            "position": item.player.position,
            "team": item.player.pro_team,
            "adp": item.player.adp,
            "projected_points": item.player.projected_points,
            "value_over_replacement": round(item.value_over_replacement, 2),
            "need_multiplier": round(item.need_multiplier, 2),
            "availability_risk": round(item.availability_risk, 3),
            "reason": item.reason,
        }
        for item in recommendations
    ]
    context = {
        "completed_round": round_number,
        "league": {
            "teams": rules.teams,
            "scoring": rules.scoring,
            "roster_slots": rules.slots(),
        },
        "my_roster": [
            {
                "player": player.name,
                "position": player.position,
                "team": player.pro_team,
            }
            for player in my_roster
        ],
        "my_position_counts": dict(Counter(player.position for player in my_roster)),
        "last_round_picks": recent_picks,
        "current_board": board,
    }
    return (
        "Review this NFL fantasy snake draft after the completed round. "
        "Select the primary pick and exactly three distinct fallbacks only from "
        "current_board. Respect the deterministic ordering, but adjust within that "
        "candidate set for roster construction, positional runs, scarcity, and likely "
        "availability. Do not add news, injuries, or players not supplied. Keep both "
        "assessment fields concise and actionable.\n"
        + json.dumps(context, ensure_ascii=True)
    )


def _generate_draft_review(
    api_key: str, model: str, prompt: str, max_output_tokens: int
) -> str:
    safe_model = urllib.parse.quote(model, safe="-_.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent"
    properties = {
        "primary_pick": {"type": "string"},
        "fallback_picks": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "roster_assessment": {"type": "string"},
        "strategy_adjustment": {"type": "string"},
    }
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties),
                    "additionalProperties": False,
                },
                "maxOutputTokens": max_output_tokens,
                "temperature": 0.1,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Gemini API returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Gemini API connection failed: {error.reason}.") from error
    try:
        return str(payload["candidates"][0]["content"]["parts"][0]["text"])
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Gemini response did not contain generated text.") from error


def analyze_draft_round(
    round_number: int,
    players: list[Player],
    picks: list[DraftPick],
    recommendations: list[Recommendation],
    rules: LeagueRules,
    *,
    api_key: str,
    model: str,
    cache_file: Path,
    budget_file: Path,
    daily_request_limit: int = 20,
    daily_token_limit: int = 100000,
    max_output_tokens: int = 1200,
    generate: object | None = None,
) -> DraftReview:
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")
    if len(recommendations) < 4:
        raise ValueError("At least four recommendations are required for a draft review.")
    prompt = _draft_prompt(round_number, players, picks, recommendations, rules)
    input_hash = hashlib.sha256(f"{model}\n{prompt}".encode("utf-8")).hexdigest()
    if cache_file.is_file():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        if cached.get("input_hash") == input_hash:
            return DraftReview(
                **{
                    **cached,
                    "fallback_picks": tuple(cached.get("fallback_picks", [])),
                }
            )
    _reserve_budget(
        budget_file,
        max(1, len(prompt.encode("utf-8")) // 4),
        daily_request_limit,
        daily_token_limit,
    )
    generator = generate or _generate_draft_review
    raw = generator(api_key, model, prompt, max_output_tokens)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Gemini draft review must be a JSON object.")
    primary = payload.get("primary_pick")
    fallbacks = payload.get("fallback_picks")
    allowed = {item.player.name for item in recommendations}
    if not isinstance(primary, str) or primary not in allowed:
        raise ValueError("Gemini draft review selected an unknown primary player.")
    if (
        not isinstance(fallbacks, list)
        or len(fallbacks) != 3
        or any(not isinstance(name, str) or name not in allowed for name in fallbacks)
        or len(set(fallbacks)) != 3
        or primary in fallbacks
    ):
        raise ValueError("Gemini draft review requires three distinct valid fallbacks.")
    for field in ("roster_assessment", "strategy_adjustment"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"Gemini draft review {field} must be nonempty text.")
    review = DraftReview(
        generated_at=datetime.now(UTC).isoformat(),
        model=model,
        input_hash=input_hash,
        round_number=round_number,
        primary_pick=primary,
        fallback_picks=tuple(fallbacks),
        roster_assessment=payload["roster_assessment"].strip(),
        strategy_adjustment=payload["strategy_adjustment"].strip(),
    )
    _atomic_json(cache_file, asdict(review))
    return review