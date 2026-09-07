from __future__ import annotations

import json
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

from .recommendations import Player


SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    "?dates={calendar_year}&limit=1000"
)


@dataclass(frozen=True)
class Game:
    game_id: str
    season: int
    season_type: int
    week: int
    starts_at: datetime
    home_team: str
    away_team: str
    completed: bool
    home_score: float | None = None
    away_score: float | None = None


@dataclass(frozen=True)
class WeeklyProjection:
    player_id: int
    opponent: str
    is_home: bool
    expected_points: float
    neutral_points: float
    fixture_adjustment: float


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_scoreboard(payload: object) -> list[Game]:
    if not isinstance(payload, Mapping):
        raise ValueError("ESPN scoreboard response must be an object.")
    games: list[Game] = []
    events = payload.get("events", [])
    if not isinstance(events, list):
        return games
    for event in events:
        if not isinstance(event, Mapping):
            continue
        competitions = event.get("competitions", [])
        if not isinstance(competitions, list) or not competitions:
            continue
        competition = competitions[0]
        if not isinstance(competition, Mapping):
            continue
        competitors = competition.get("competitors", [])
        if not isinstance(competitors, list):
            continue
        by_venue = {
            str(item.get("homeAway")): item
            for item in competitors
            if isinstance(item, Mapping)
        }
        home = by_venue.get("home")
        away = by_venue.get("away")
        if home is None or away is None:
            continue
        home_team = home.get("team", {})
        away_team = away.get("team", {})
        season = event.get("season", {})
        status = event.get("status", {})
        week = event.get("week", {})
        if not all(isinstance(item, Mapping) for item in (home_team, away_team, season, status, week)):
            continue
        starts_at = datetime.fromisoformat(str(event.get("date", "")).replace("Z", "+00:00"))
        status_type = status.get("type", {})
        games.append(
            Game(
                game_id=str(event.get("id", "")),
                season=int(season.get("year", 0)),
                season_type=int(season.get("type", 0)),
                week=int(week.get("number", 0)),
                starts_at=starts_at.astimezone(UTC),
                home_team=str(home_team.get("abbreviation", "")),
                away_team=str(away_team.get("abbreviation", "")),
                completed=bool(status_type.get("completed", False)) if isinstance(status_type, Mapping) else False,
                home_score=_number(home.get("score")),
                away_score=_number(away.get("score")),
            )
        )
    return games


def fetch_games(season: int) -> list[Game]:
    games: dict[str, Game] = {}
    for calendar_year in (season - 1, season, season + 1):
        with urllib.request.urlopen(
            SCOREBOARD_URL.format(calendar_year=calendar_year), timeout=45
        ) as response:
            for game in parse_scoreboard(json.loads(response.read())):
                if game.season in {season - 1, season} and game.season_type == 2:
                    games[game.game_id] = game
    return list(games.values())


def _team_strengths(games: list[Game]) -> dict[str, tuple[float, float]]:
    completed = [
        game
        for game in games
        if game.completed and game.home_score is not None and game.away_score is not None
    ]
    if not completed:
        return {}
    sample = completed
    scored: dict[str, list[float]] = defaultdict(list)
    allowed: dict[str, list[float]] = defaultdict(list)
    for game in sample:
        scored[game.home_team].append(float(game.home_score))
        allowed[game.home_team].append(float(game.away_score))
        scored[game.away_team].append(float(game.away_score))
        allowed[game.away_team].append(float(game.home_score))
    league_average = sum(sum(values) for values in scored.values()) / sum(
        len(values) for values in scored.values()
    )
    strengths: dict[str, tuple[float, float]] = {}
    for team, values in scored.items():
        games_played = len(values)
        weight = games_played / (games_played + 4)
        attack_raw = (sum(values) / games_played) / league_average
        defense_raw = league_average / max(1.0, sum(allowed[team]) / games_played)
        strengths[team] = (
            1.0 + (attack_raw - 1.0) * weight,
            1.0 + (defense_raw - 1.0) * weight,
        )
    return strengths


def fixture_multiplier(position: str, opponent_strength: tuple[float, float], is_home: bool) -> float:
    opponent_attack, opponent_defense = opponent_strength
    strength = opponent_attack if position == "D/ST" else opponent_defense
    venue_adjustment = 0.03 if is_home else -0.03
    return max(0.78, min(1.18, 1.0 - 0.18 * (strength - 1.0) + venue_adjustment))


def project_week(
    players: list[Player], games: list[Game], now: datetime | None = None
) -> dict[int, WeeklyProjection]:
    current_time = now or datetime.now(UTC)
    upcoming = [game for game in games if game.season_type == 2 and not game.completed and game.starts_at >= current_time]
    if not upcoming:
        return {}
    next_game = min(upcoming, key=lambda game: game.starts_at)
    fixtures = [game for game in upcoming if game.season == next_game.season and game.week == next_game.week]
    strengths = _team_strengths(games)
    result: dict[int, WeeklyProjection] = {}
    for player in players:
        fixture = next(
            (game for game in fixtures if player.pro_team in {game.home_team, game.away_team}),
            None,
        )
        if fixture is None or player.projected_points <= 0:
            continue
        is_home = player.pro_team == fixture.home_team
        opponent = fixture.away_team if is_home else fixture.home_team
        neutral = player.projected_points / 17.0
        multiplier = fixture_multiplier(player.position, strengths.get(opponent, (1.0, 1.0)), is_home)
        expected = neutral * multiplier
        result[player.player_id] = WeeklyProjection(
            player_id=player.player_id,
            opponent=opponent,
            is_home=is_home,
            expected_points=expected,
            neutral_points=neutral,
            fixture_adjustment=expected - neutral,
        )
    return result