from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .config import Config
from .recommendations import DraftPick, Player, Recommendation, next_pick_for_position


def _tier(value_score: float, best_score: float) -> int:
    gap = best_score - value_score
    return 1 + max(0, int(gap // 15))


def write_dossier(
    path: Path,
    config: Config,
    players: list[Player],
    picks: list[DraftPick],
    recommendations: list[Recommendation],
    *,
    source: str,
    source_updated_at: str,
) -> None:
    by_id = {player.player_id: player for player in players}
    my_players = [by_id[pick.player_id] for pick in picks if pick.is_mine and pick.player_id in by_id]
    drafted = [by_id[pick.player_id] for pick in picks if pick.player_id in by_id]
    best_score = recommendations[0].value_score if recommendations else 0.0
    next_mine = next_pick_for_position(
        len(picks), config.rules.teams, config.draft_position
    )
    lines = [
        "# ESPN fantasy football draft-room context",
        "",
        f"Generated: `{datetime.now(UTC).isoformat()}`",
        f"Player source: `{source}` (updated `{source_updated_at}`)",
        "",
        "## Agent instructions",
        "",
        "Use this file as the current source of truth. Recommend one primary pick and three contingencies. "
        "Respect roster construction, value over replacement, positional scarcity, ADP, injuries, and "
        "which players are already drafted. State what new information would change the recommendation.",
        "",
        "## League configuration",
        "",
        f"- Season: **{config.season}**",
        f"- Teams: **{config.rules.teams}**",
        f"- Scoring preset: **{config.rules.scoring.upper()}**",
        f"- Matchup format: **{config.matchup.replace('_', ' ').title()}**",
        f"- Draft type: **{config.draft_type.title()}**",
        f"- Draft position: **{config.draft_position or 'unknown'}**",
        f"- My ESPN team number: **{config.my_team or 'not configured'}**",
        "- Roster: " + ", ".join(f"{position} {count}" for position, count in config.rules.roster_slots),
        "",
        "## Live state",
        "",
        f"- Picks recorded: **{len(picks)}**",
        f"- Next overall pick: **{len(picks) + 1}**",
        f"- My next pick: **{next_mine or 'unknown until draft position is configured'}**",
        f"- My roster ({len(my_players)}): "
        + (", ".join(f"{player.name} ({player.position})" for player in my_players) or "empty"),
        "- My position counts: "
        + (", ".join(f"{key} {value}" for key, value in sorted(Counter(p.position for p in my_players).items())) or "none"),
        "",
        "## Current recommendation board",
        "",
        "| # | Tier | Player | Pos | NFL | Proj | VOR | Need | ADP | Status | Why |",
        "|---:|---:|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for index, item in enumerate(recommendations, 1):
        player = item.player
        adp = f"{player.adp:.1f}" if player.adp is not None else "-"
        projection = f"{player.projected_points:.1f}" if player.projected_points > 0 else "-"
        lines.append(
            f"| {index} | {_tier(item.value_score, best_score)} | {player.name} | "
            f"{player.position} | {player.pro_team} | {projection} | "
            f"{item.value_over_replacement:+.1f} | {item.need_multiplier:.2f} | "
            f"{adp} | {player.injury_status} | {item.reason} |"
        )
    lines.extend(["", "## Recorded picks", ""])
    if not drafted:
        lines.append("No picks recorded yet.")
    else:
        lines.extend(
            f"- {pick.overall}. {by_id[pick.player_id].name} ({by_id[pick.player_id].position})"
            + (" — my pick" if pick.is_mine else "")
            for pick in picks
            if pick.player_id in by_id
        )
    lines.extend(
        [
            "",
            "## Draft principles",
            "",
            "- Prefer meaningful value over replacement, not raw projected points alone.",
            "- Use tiers to avoid reaching when several comparable players remain.",
            "- Delay kicker and defense unless the remaining board no longer offers useful upside.",
            "- Treat ADP as an availability estimate, not as player quality.",
            "- Recalculate after every pick; positional runs and your roster change the answer.",
            "- Verify late injuries, suspensions, depth-chart changes, and scoring rules during the draft.",
            "",
            "## Suggested live prompt",
            "",
            "> Using this draft-room context, tell me the best pick now and three fallbacks. "
            "Explain the roster fit, opportunity cost, likely availability at my next pick, and key risks.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")