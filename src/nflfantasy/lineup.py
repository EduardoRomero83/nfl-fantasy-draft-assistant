from __future__ import annotations

from dataclasses import dataclass

from .recommendations import FLEX_POSITIONS, LeagueRules, Player


@dataclass(frozen=True)
class LineupSelection:
    slot: str
    player: Player


@dataclass(frozen=True)
class LineupRecommendation:
    starters: tuple[LineupSelection, ...]
    bench: tuple[Player, ...]
    expected_points: float
    missing_projections: tuple[Player, ...]


def recommend_lineup(
    roster: list[Player],
    rules: LeagueRules,
    projected_points: dict[int, float] | None = None,
) -> LineupRecommendation:
    if len({player.player_id for player in roster}) != len(roster):
        raise ValueError("Roster contains duplicate players.")

    def points(player: Player) -> float:
        return projected_points.get(player.player_id, 0.0) if projected_points is not None else player.projected_points

    remaining = list(roster)
    starters: list[LineupSelection] = []
    slots = rules.slots()
    for position in ("QB", "RB", "WR", "TE", "K", "D/ST"):
        candidates = sorted(
            (player for player in remaining if player.position == position),
            key=points,
            reverse=True,
        )
        for player in candidates[: slots.get(position, 0)]:
            starters.append(LineupSelection(position, player))
            remaining.remove(player)

    flex_candidates = sorted(
        (player for player in remaining if player.position in FLEX_POSITIONS),
        key=points,
        reverse=True,
    )
    for player in flex_candidates[: slots.get("FLEX", 0)]:
        starters.append(LineupSelection("FLEX", player))
        remaining.remove(player)

    bench = tuple(sorted(remaining, key=points, reverse=True))
    missing = tuple(player for player in roster if points(player) <= 0)
    return LineupRecommendation(
        starters=tuple(starters),
        bench=bench,
        expected_points=sum(points(item.player) for item in starters),
        missing_projections=missing,
    )