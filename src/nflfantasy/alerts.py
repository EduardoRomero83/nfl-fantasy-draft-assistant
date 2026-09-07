from __future__ import annotations

from datetime import UTC, datetime

from .config import Config
from .lineup import recommend_lineup
from .recommendations import DraftPick, Player, recommend_players


def build_alert(
    config: Config,
    players: list[Player],
    picks: list[DraftPick],
    roster_ids: list[int],
) -> str:
    lines = [
        "NFL FANTASY THURSDAY CHECK",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "Schedule: Thursday at 2:00 PM local computer time",
        "",
    ]
    by_id = {player.player_id: player for player in players}
    roster = [by_id[player_id] for player_id in roster_ids if player_id in by_id]
    if roster:
        recommendation = recommend_lineup(roster, config.rules)
        lines.extend(
            [
                "RECOMMENDED STARTERS",
                *(
                    f"{item.slot:<4} {item.player.name:<28} "
                    + (
                        f"{item.player.projected_points:>7.1f} expected season points"
                        if item.player.projected_points > 0
                        else "    N/A expected season points"
                    )
                    for item in recommendation.starters
                ),
                "",
                f"Expected starter season total: {recommendation.expected_points:.1f}",
                "Bench: " + (", ".join(player.name for player in recommendation.bench) or "none"),
            ]
        )
        if recommendation.missing_projections:
            lines.extend(
                [
                    "",
                    "ACTION REQUIRED",
                    "ESPN has not published trustworthy projections for: "
                    + ", ".join(player.name for player in recommendation.missing_projections),
                    "Check injuries, Thursday-night players, and ESPN's live weekly outlook before setting the lineup.",
                ]
            )
    else:
        recommendations = recommend_players(
            players,
            picks,
            config.rules,
            limit=10,
            draft_position=config.draft_position,
        )
        lines.extend(["DRAFT BOARD", "No post-draft roster is configured yet."])
        lines.extend(
            f"{index:>2}. {item.player.name} ({item.player.position}, {item.player.pro_team}) "
            f"ADP {item.player.adp:.1f} - {item.reason}"
            for index, item in enumerate(recommendations, 1)
            if item.player.adp is not None
        )
        lines.extend(
            [
                "",
                "ACTION REQUIRED",
                "During the draft, mark your selections as mine. Afterward, build the roster from those picks.",
            ]
        )
    lines.extend(
        [
            "",
            "DATA LIMITATION",
            "This alert uses ESPN's public data without an ESPN account. Weekly expected points will replace season totals when ESPN publishes them reliably.",
            "",
        ]
    )
    return "\n".join(lines)