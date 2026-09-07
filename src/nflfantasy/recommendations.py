from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import exp, sqrt


FLEX_POSITIONS = frozenset({"RB", "WR", "TE"})


@dataclass(frozen=True)
class LeagueRules:
    teams: int = 14
    roster_slots: tuple[tuple[str, int], ...] = (
        ("QB", 1),
        ("RB", 2),
        ("WR", 2),
        ("TE", 1),
        ("FLEX", 1),
        ("D/ST", 1),
        ("K", 1),
        ("BE", 7),
    )
    scoring: str = "ppr"

    def slots(self) -> dict[str, int]:
        return dict(self.roster_slots)


@dataclass(frozen=True)
class Player:
    player_id: int
    name: str
    position: str
    pro_team: str
    projected_points: float
    adp: float | None = None
    auction_value: float | None = None
    injury_status: str = "ACTIVE"
    source_rank: int | None = None


@dataclass(frozen=True)
class DraftPick:
    overall: int
    player_id: int
    fantasy_team: int | None = None
    is_mine: bool = False


@dataclass(frozen=True)
class Recommendation:
    player: Player
    value_score: float
    value_over_replacement: float
    need_multiplier: float
    availability_risk: float
    reason: str


def next_pick_for_position(picks_made: int, teams: int, draft_position: int) -> int | None:
    if draft_position < 1 or draft_position > teams:
        return None
    for overall in range(picks_made + 1, picks_made + teams * 2 + 1):
        round_number = (overall - 1) // teams + 1
        slot = (overall - 1) % teams + 1
        target_slot = draft_position if round_number % 2 else teams - draft_position + 1
        if slot == target_slot:
            return overall
    return None


def _position_counts(players: list[Player]) -> Counter[str]:
    return Counter(player.position for player in players)


def _quality(player: Player, use_projections: bool) -> float:
    if use_projections:
        return player.projected_points
    return max(0.0, 400.0 - player.adp) if player.adp is not None else 0.0


def _injury_penalty(status: str) -> float:
    normalized = status.upper().strip()
    if normalized in {"", "ACTIVE", "NORMAL", "HEALTHY"}:
        return 0.0
    if normalized == "QUESTIONABLE":
        return 2.0
    if normalized == "DOUBTFUL":
        return 8.0
    if normalized in {"OUT", "INJURY_RESERVE", "IR", "SUSPENSION", "SUSPENDED"}:
        return 15.0
    return 5.0


def _replacement_values(
    players: list[Player], rules: LeagueRules, use_projections: bool
) -> dict[str, float]:
    slots = rules.slots()
    demand = {
        "QB": rules.teams * slots.get("QB", 1),
        "RB": rules.teams * (slots.get("RB", 2) + slots.get("FLEX", 1) * 0.45),
        "WR": rules.teams * (slots.get("WR", 2) + slots.get("FLEX", 1) * 0.45),
        "TE": rules.teams * (slots.get("TE", 1) + slots.get("FLEX", 1) * 0.10),
        "D/ST": rules.teams * slots.get("D/ST", 1),
        "K": rules.teams * slots.get("K", 1),
    }
    result: dict[str, float] = {}
    for position, required in demand.items():
        values = sorted(
            (
                _quality(player, use_projections)
                for player in players
                if player.position == position and _quality(player, use_projections) > 0
            ),
            reverse=True,
        )
        if not values:
            result[position] = 0.0
            continue
        index = min(len(values) - 1, max(0, round(required) - 1))
        result[position] = values[index]
    return result


def _need_multiplier(position: str, roster: list[Player], rules: LeagueRules) -> float:
    counts = _position_counts(roster)
    slots = rules.slots()
    if position in {"K", "D/ST"}:
        return 0.35 if not counts[position] else 0.05
    required = slots.get(position, 0)
    if position in FLEX_POSITIONS:
        flex_filled = sum(counts[item] for item in FLEX_POSITIONS)
        required += max(0.0, slots.get("FLEX", 0) / len(FLEX_POSITIONS))
        if flex_filled < sum(slots.get(item, 0) for item in FLEX_POSITIONS):
            required += 0.5
    deficit = max(0.0, required - counts[position])
    if deficit:
        return 1.0 + min(0.35, deficit * 0.15)
    return max(0.72, 1.0 - 0.10 * (counts[position] - required + 1))


def recommend_players(
    players: list[Player],
    picks: list[DraftPick],
    rules: LeagueRules,
    *,
    limit: int = 12,
    draft_position: int = 0,
) -> list[Recommendation]:
    drafted_ids = {pick.player_id for pick in picks}
    by_id = {player.player_id: player for player in players}
    my_roster = [
        by_id[pick.player_id]
        for pick in picks
        if pick.is_mine and pick.player_id in by_id
    ]
    projection_count = sum(player.projected_points > 0 for player in players)
    use_projections = projection_count >= max(100, rules.teams * 8)
    available = [
        player
        for player in players
        if player.player_id not in drafted_ids
        and (player.projected_points > 0 or (player.adp is not None and player.adp > 0))
    ]
    replacement = _replacement_values(players, rules, use_projections)
    next_overall = len(picks) + 1
    next_my_pick = next_pick_for_position(len(picks), rules.teams, draft_position)
    results: list[Recommendation] = []
    for player in available:
        vor = _quality(player, use_projections) - replacement.get(player.position, 0.0)
        need = _need_multiplier(player.position, my_roster, rules)
        adp_gap = 0.0 if player.adp is None else next_overall - player.adp
        if player.adp is None or next_my_pick is None or next_my_pick <= next_overall:
            availability_probability = 1.0
        else:
            availability_probability = 1.0 / (
                1.0 + exp((next_my_pick - player.adp) / sqrt(rules.teams * 2))
            )
        availability_risk = 1.0 - availability_probability
        injury_penalty = _injury_penalty(player.injury_status)
        if use_projections:
            score = (
                vor * need * (0.35 + 0.65 * availability_probability)
                + adp_gap * 0.35
                - injury_penalty
            )
        else:
            score = (
                -(player.adp or 400.0)
                + (need - 1.0) * 20.0
                - availability_risk * 3.0
                - injury_penalty
            )
        basis = "points" if use_projections else "consensus value"
        availability = (
            f" estimated {availability_probability:.0%} chance to reach pick {next_my_pick};"
            if next_my_pick is not None and next_my_pick > next_overall
            else ""
        )
        reason = (
            f"{vor:+.1f} {basis} over {player.position} replacement; "
            f"roster multiplier {need:.2f};{availability} "
            + (f"ADP {player.adp:.1f}." if player.adp is not None else "ADP unavailable.")
            + (
                f" ESPN status {player.injury_status} applies a {injury_penalty:.0f}-point caution."
                if injury_penalty
                else ""
            )
        )
        results.append(
            Recommendation(player, score, vor, need, availability_risk, reason)
        )
    return sorted(
        results,
        key=lambda item: (
            item.value_score,
            item.value_over_replacement,
            item.player.projected_points,
        ),
        reverse=True,
    )[:limit]