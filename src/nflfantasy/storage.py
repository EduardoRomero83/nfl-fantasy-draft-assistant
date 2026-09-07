from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .recommendations import DraftPick, Player


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_players(path: Path, players: list[Player], source: str) -> None:
    _atomic_write(
        path,
        {
            "updated_at": datetime.now(UTC).isoformat(),
            "source": source,
            "players": [asdict(player) for player in players],
        },
    )


def load_players(path: Path) -> list[Player]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Player(**item) for item in payload.get("players", [])]


def load_player_metadata(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_picks(path: Path, picks: list[DraftPick]) -> None:
    _atomic_write(path, {"picks": [asdict(pick) for pick in picks]})


def load_picks(path: Path) -> list[DraftPick]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [DraftPick(**item) for item in payload.get("picks", [])]


def save_roster(path: Path, player_ids: list[int]) -> None:
    _atomic_write(path, {"player_ids": player_ids})


def load_roster(path: Path) -> list[int]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [int(player_id) for player_id in payload.get("player_ids", [])]