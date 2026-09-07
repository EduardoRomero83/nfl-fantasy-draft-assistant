from __future__ import annotations

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
smtp_host = ""
smtp_port = 587
starttls = true
sender = ""
recipient = ""
subject = "NFL fantasy draft board"
"""


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    starttls: bool
    sender: str
    recipient: str
    subject: str


@dataclass(frozen=True)
class Config:
    season: int
    matchup: str
    draft_type: str
    my_team: int
    draft_position: int
    rules: LeagueRules
    email: EmailConfig | None = None


def ensure_config(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return True


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
    if email_payload and any(str(email_payload.get(key, "")) for key in ("smtp_host", "sender", "recipient")):
        smtp_host = str(email_payload.get("smtp_host", "")).strip()
        sender = str(email_payload.get("sender", "")).strip()
        recipient = str(email_payload.get("recipient", "")).strip()
        if not smtp_host or not sender or not recipient:
            raise ValueError("[email] requires smtp_host, sender, and recipient together.")
        smtp_port = int(email_payload.get("smtp_port", 587))
        if not 1 <= smtp_port <= 65535:
            raise ValueError("email.smtp_port must be between 1 and 65535.")
        email = EmailConfig(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            starttls=bool(email_payload.get("starttls", True)),
            sender=sender,
            recipient=recipient,
            subject=str(email_payload.get("subject", "NFL fantasy draft board")),
        )
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
    )