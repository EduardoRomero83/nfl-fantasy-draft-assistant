from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .recommendations import LeagueRules


DEFAULT_CONFIG = """season = 2026
teams = 14
scoring = "ppr"
matchup = "head_to_head"
draft_type = "snake"
my_team = 0
draft_position = 0

[roster]
QB = 1
RB = 2
WR = 2
TE = 1
FLEX = 1
K = 1
BE = 7
"D/ST" = 1

[email]
recipient = ""
subject = "NFL fantasy Thursday alert"

[gemini]
enabled = false
model = "gemini-2.5-flash"
max_queries = 4
max_articles = 12
daily_request_limit = 2
daily_token_limit = 20000
"""


@dataclass(frozen=True)
class EmailConfig:
    recipient: str
    subject: str


@dataclass(frozen=True)
class GeminiConfig:
    enabled: bool = False
    model: str = "gemini-2.5-flash"
    max_queries: int = 4
    max_articles: int = 12
    daily_request_limit: int = 2
    daily_token_limit: int = 20000


@dataclass(frozen=True)
class Config:
    season: int
    matchup: str
    draft_type: str
    my_team: int
    draft_position: int
    rules: LeagueRules
    email: EmailConfig | None = None
    gemini: GeminiConfig = GeminiConfig()


def ensure_config(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return True


def update_draft_position(path: Path, draft_position: int) -> Config:
    config = load_config(path)
    if not 1 <= draft_position <= config.rules.teams:
        raise ValueError(
            f"draft_position must be between 1 and {config.rules.teams}."
        )
    source = path.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r"(?m)^(draft_position\s*=\s*)\d+(\s*(?:#.*)?)$",
        rf"\g<1>{draft_position}\g<2>",
        source,
        count=1,
    )
    if replacements != 1:
        raise ValueError("config.toml is missing the root draft_position setting.")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(updated, encoding="utf-8")
    temporary.replace(path)
    return load_config(path)


def load_config(path: Path) -> Config:
    with path.open("rb") as stream:
        payload = tomllib.load(stream)
    roster = payload.get("roster", {})
    if not isinstance(roster, dict):
        raise ValueError("[roster] must be a TOML table.")
    slots = tuple((str(key).upper(), int(value)) for key, value in roster.items())
    teams = int(payload.get("teams", 14))
    scoring = str(payload.get("scoring", "ppr")).lower()
    matchup = str(payload.get("matchup", "head_to_head")).lower()
    draft_type = str(payload.get("draft_type", "snake")).lower()
    my_team = int(payload.get("my_team", 0))
    draft_position = int(payload.get("draft_position", 0))
    if teams < 2:
        raise ValueError("teams must be at least 2.")
    if scoring not in {"ppr", "half", "standard"}:
        raise ValueError("scoring must be ppr, half, or standard.")
    if matchup != "head_to_head":
        raise ValueError("matchup must be head_to_head.")
    if draft_type != "snake":
        raise ValueError("draft_type must be snake.")
    if not 0 <= my_team <= teams:
        raise ValueError("my_team must be 0 (unknown) or a team number.")
    if not 0 <= draft_position <= teams:
        raise ValueError("draft_position must be 0 (unknown) or a draft slot.")
    if not slots or any(count < 0 for _, count in slots):
        raise ValueError("[roster] must contain non-negative slot counts.")
    email_payload = payload.get("email", {})
    if not isinstance(email_payload, dict):
        raise ValueError("[email] must be a TOML table.")
    email = None
    if email_payload and str(email_payload.get("recipient", "")).strip():
        recipient = str(email_payload.get("recipient", "")).strip()
        if "@" not in recipient or recipient.startswith("@") or recipient.endswith("@"):
            raise ValueError("email.recipient must be a valid email address.")
        email = EmailConfig(
            recipient=recipient,
            subject=str(email_payload.get("subject", "NFL fantasy Thursday alert")),
        )
    gemini_payload = payload.get("gemini", {})
    if not isinstance(gemini_payload, dict):
        raise ValueError("[gemini] must be a TOML table.")
    gemini = GeminiConfig(
        enabled=bool(gemini_payload.get("enabled", False)),
        model=str(gemini_payload.get("model", "gemini-2.5-flash")).strip(),
        max_queries=int(gemini_payload.get("max_queries", 4)),
        max_articles=int(gemini_payload.get("max_articles", 12)),
        daily_request_limit=int(gemini_payload.get("daily_request_limit", 2)),
        daily_token_limit=int(gemini_payload.get("daily_token_limit", 20000)),
    )
    if not gemini.model or not 1 <= gemini.max_queries <= 10 or not 1 <= gemini.max_articles <= 30:
        raise ValueError("[gemini] requires a model, 1-10 queries, and 1-30 articles.")
    if gemini.daily_request_limit < 1 or gemini.daily_token_limit < 1000:
        raise ValueError("Gemini daily limits must allow at least 1 request and 1000 tokens.")
    return Config(
        season=int(payload.get("season", 2026)),
        matchup=matchup,
        draft_type=draft_type,
        my_team=my_team,
        draft_position=draft_position,
        rules=LeagueRules(
            teams=teams,
            roster_slots=slots,
            scoring=scoring,
        ),
        email=email,
        gemini=gemini,
    )