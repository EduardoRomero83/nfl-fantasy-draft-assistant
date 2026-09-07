from __future__ import annotations

import json
import urllib.request
from typing import Mapping

from .recommendations import Player


ESPN_PLAYERS_URL = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"
    "?scoringPeriodId=0&view=kona_player_info"
)
POSITION_NAMES = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}
MAX_SEASON_PROJECTION = {"QB": 600.0, "RB": 500.0, "WR": 500.0, "TE": 400.0, "K": 300.0, "D/ST": 300.0}
PRO_TEAM_NAMES = {
    0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL",
    7: "DEN", 8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV",
    14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ",
    21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA",
    27: "TB", 28: "WSH", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _projection(entry: Mapping[str, object], season: int) -> float:
    stats = entry.get("stats", [])
    if isinstance(stats, list):
        projected = [
            _number(item.get("appliedTotal"))
            for item in stats
            if isinstance(item, Mapping)
            and int(item.get("seasonId", 0)) == season
            and int(item.get("scoringPeriodId", -1)) == 0
            and int(item.get("statSourceId", 0)) == 1
            and int(item.get("statSplitTypeId", -1)) == 0
        ]
        valid = [value for value in projected if value is not None]
        if valid:
            return max(valid)
    return 0.0


def parse_players(payload: object, season: int = 2026) -> list[Player]:
    if not isinstance(payload, list):
        raise ValueError("ESPN player response must be a list.")
    players: list[Player] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        player = item.get("player", item)
        if not isinstance(player, Mapping):
            continue
        position = POSITION_NAMES.get(int(player.get("defaultPositionId", 0)))
        player_id = int(player.get("id", 0))
        name = str(player.get("fullName", "")).strip()
        if not position or not player_id or not name:
            continue
        projection = _projection(player, season)
        ownership = player.get("ownership", {})
        adp = _number(ownership.get("averageDraftPosition")) if isinstance(ownership, Mapping) else None
        auction = _number(ownership.get("auctionValueAverage")) if isinstance(ownership, Mapping) else None
        rankings = player.get("rankings", {})
        source_rank = None
        if isinstance(rankings, Mapping):
            ranking_values = [
                int(value.get("overallRanking"))
                for value in rankings.values()
                if isinstance(value, Mapping) and value.get("overallRanking") is not None
            ]
            source_rank = min(ranking_values) if ranking_values else None
        players.append(
            Player(
                player_id=player_id,
                name=name,
                position=position,
                pro_team=PRO_TEAM_NAMES.get(int(player.get("proTeamId", 0)), "FA"),
                projected_points=(
                    projection
                    if 0 < projection <= MAX_SEASON_PROJECTION[position]
                    else 0.0
                ),
                adp=adp,
                auction_value=auction,
                injury_status=str(player.get("injuryStatus", "ACTIVE")),
                source_rank=source_rank,
            )
        )
    if not players:
        raise ValueError("ESPN response contained no recognized fantasy players.")
    return players


def fetch_players(season: int, *, limit: int = 1500) -> list[Player]:
    fantasy_filter = {
        "players": {
            "limit": limit,
            "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
        }
    }
    request = urllib.request.Request(
        ESPN_PLAYERS_URL.format(season=season),
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Fantasy-Filter": json.dumps(fantasy_filter, separators=(",", ":")),
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return parse_players(json.loads(response.read()), season)