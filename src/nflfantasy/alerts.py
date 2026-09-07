from __future__ import annotations

from datetime import UTC, datetime

from .config import Config
from .intelligence import IntelligenceReport
from .lineup import recommend_lineup
from .news import NewsArticle
from .recommendations import DraftPick, Player, recommend_players


def build_alert(
    config: Config,
    players: list[Player],
    picks: list[DraftPick],
    roster_ids: list[int],
    intelligence: IntelligenceReport | None = None,
    articles: list[NewsArticle] | None = None,
    intelligence_warning: str | None = None,
) -> str:
    lines = [
        "NFL FANTASY THURSDAY CHECK",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "Schedule: Thursday at 2:00 PM local computer time",
        "",
    ]
    by_id = {player.player_id: player for player in players}
    roster = [by_id[player_id] for player_id in roster_ids if player_id in by_id]
    baseline = recommend_lineup(roster, config.rules) if roster else None
    unavailable = {
        insight.player_name
        for insight in (intelligence.insights if intelligence else ())
        if insight.status in {"out", "unlikely"}
        and insight.start_likelihood <= 0.25
        and insight.confidence >= 0.75
    }
    if roster:
        recommendation = recommend_lineup(
            [player for player in roster if player.name not in unavailable],
            config.rules,
        )
        baseline_starter_ids = {
            item.player.player_id for item in baseline.starters
        } if baseline else set()
        promoted = [
            item.player
            for item in recommendation.starters
            if item.player.player_id not in baseline_starter_ids
        ]
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
        if unavailable:
            lines.append(
                "Withheld for strong availability risk: " + ", ".join(sorted(unavailable))
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
    if intelligence and intelligence.insights:
        drafted_ids = {pick.player_id for pick in picks}
        alternatives = recommend_players(
            [player for player in players if player.player_id not in set(roster_ids)],
            picks,
            config.rules,
            limit=20,
            draft_position=config.draft_position,
        )
        lines.extend(["", "NEWS AND START LIKELIHOOD"])
        for insight in intelligence.insights:
            lines.append(
                f"{insight.player_name}: {insight.status.upper()} | "
                f"start likelihood {insight.start_likelihood:.0%} | {insight.action.upper()}"
            )
            lines.append(f"  {insight.injury_summary} {insight.explanation}")
            player = next((item for item in players if item.name == insight.player_name), None)
            if insight.action in {"sit", "avoid", "monitor"} and player is not None:
                was_starter = bool(
                    baseline
                    and player.player_id
                    in {item.player.player_id for item in baseline.starters}
                )
                roster_replacement = next(
                    (
                        candidate
                        for candidate in (promoted if roster else [])
                        if candidate.position == player.position
                    ),
                    None,
                ) if was_starter else None
                if roster_replacement is None and was_starter and player.position in {"RB", "WR", "TE"}:
                    roster_replacement = next(
                        (
                            candidate
                            for candidate in promoted
                            if candidate.position in {"RB", "WR", "TE"}
                        ),
                        None,
                    )
                replacement = roster_replacement or (next(
                    (
                        item.player
                        for item in alternatives
                        if item.player.player_id not in drafted_ids
                        and item.player.position == player.position
                    ),
                    None,
                ) if player.player_id not in set(roster_ids) or was_starter else None)
                if replacement is not None:
                    lines.append(
                        f"  Suggested replacement: {replacement.name} ({replacement.position}, {replacement.pro_team})"
                    )
            for title in insight.evidence_titles:
                article = next(
                    (
                        item
                        for item in articles or []
                        if item.title == title and insight.player_name in item.entities
                    ),
                    None,
                )
                lines.append(f"  Source: {title}" + (f" - {article.url}" if article else ""))
    elif intelligence_warning:
        lines.extend(["", "NEWS INTELLIGENCE", f"Unavailable: {intelligence_warning}", "ESPN-only recommendations remain in effect."])
    lines.extend(
        [
            "",
            "DATA LIMITATION",
            "This alert uses ESPN's public data without an ESPN account. Weekly expected points will replace season totals when ESPN publishes them reliably.",
            "",
        ]
    )
    return "\n".join(lines)