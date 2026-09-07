from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alerts import build_alert
from .config import ensure_config, load_config
from .dossier import write_dossier
from .email_report import send_email_report
from .espn import fetch_players, parse_players
from .lineup import recommend_lineup
from .intelligence import analyze_news, load_api_key
from .news import fetch_news
from .paths import AppPaths
from .recommendations import DraftPick, Player, next_pick_for_position, recommend_players
from .setup_wizard import run_setup_wizard
from .scheduler import install_windows_task, remove_windows_task, task_status
from .storage import (
    load_picks,
    load_player_metadata,
    load_players,
    save_picks,
    save_players,
    load_roster,
    save_roster,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nflfantasy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create private local configuration.")
    subparsers.add_parser("configure", help="Answer prompts to configure the assistant.")
    subparsers.add_parser("paths", help="Show local data paths.")
    subparsers.add_parser("doctor", help="Validate configuration and draft data.")
    refresh = subparsers.add_parser("refresh", help="Refresh the public ESPN player pool.")
    refresh.add_argument("--input", type=Path, help="Import a saved ESPN JSON response instead.")
    board = subparsers.add_parser("board", help="Show recommendations for the next pick.")
    board.add_argument("--limit", type=int, default=20)
    search = subparsers.add_parser("search", help="Find a player in the current ESPN pool.")
    search.add_argument("query")
    pick = subparsers.add_parser("pick", help="Record the next drafted player.")
    pick.add_argument("player")
    pick.add_argument("--mine", action="store_true", help="Mark this as your pick.")
    pick.add_argument("--team", type=int, help="Fantasy team number, if known.")
    subparsers.add_parser("undo", help="Remove the latest recorded pick.")
    reset = subparsers.add_parser("reset", help="Clear all recorded picks.")
    reset.add_argument("--yes", action="store_true", required=True)
    dossier = subparsers.add_parser("dossier", help="Write the agent-ready Markdown context.")
    dossier.add_argument("--limit", type=int, default=75)
    email = subparsers.add_parser("email", help="Email the current draft report on demand.")
    email.add_argument("--limit", type=int, default=75)
    roster = subparsers.add_parser("roster", help="Show or set the post-draft roster.")
    roster.add_argument("players", nargs="*", help="Player names or ESPN IDs.")
    roster.add_argument("--from-my-picks", action="store_true", help="Use picks recorded with --mine.")
    subparsers.add_parser("lineup", help="Recommend starters by full-season expected points.")
    alert = subparsers.add_parser("alert", help="Write a preview of the Thursday alert.")
    alert.add_argument("--refresh", action="store_true", help="Refresh ESPN first.")
    alert.add_argument("--send", action="store_true", help="Email the alert after writing it.")
    subparsers.add_parser("scheduled-alert", help=argparse.SUPPRESS)
    subparsers.add_parser("schedule-install", help="Schedule Thursday alerts for 2:00 PM.")
    subparsers.add_parser("schedule-remove", help="Remove the Thursday alert task.")
    subparsers.add_parser("schedule-status", help="Show the Thursday alert task status.")
    subparsers.add_parser("setup", help="Initialize, refresh ESPN, and write the first dossier.")
    return parser


def _find_player(players: list[Player], query: str) -> Player:
    if query.isdigit():
        exact_id = [player for player in players if player.player_id == int(query)]
        if exact_id:
            return exact_id[0]
    normalized = query.casefold().strip()
    exact = [player for player in players if player.name.casefold() == normalized]
    if len(exact) == 1:
        return exact[0]
    matches = [player for player in players if normalized in player.name.casefold()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"No player matches {query!r}.")
    names = ", ".join(f"{player.name} [{player.player_id}]" for player in matches[:10])
    raise ValueError(f"Player name is ambiguous: {names}")


def _print_board(players: list[Player], picks: list[DraftPick], config: object, limit: int) -> None:
    recommendations = recommend_players(
        players,
        picks,
        config.rules,
        limit=limit,
        draft_position=config.draft_position,
    )
    next_mine = next_pick_for_position(len(picks), config.rules.teams, config.draft_position)
    print(
        f"Next overall pick: {len(picks) + 1} | "
        f"My next pick: {next_mine or 'unknown'} | "
        f"My roster picks: {sum(pick.is_mine for pick in picks)}"
    )
    for index, item in enumerate(recommendations, 1):
        player = item.player
        adp = f"{player.adp:.1f}" if player.adp is not None else "-"
        projection = f"{player.projected_points:.1f}" if player.projected_points > 0 else "-"
        print(
            f"{index:>2}. {player.name:<26} {player.position:<4} {player.pro_team:<3} "
            f"Proj {projection:>6} Value {item.value_over_replacement:>+6.1f} "
            f"ADP {adp:>6} | {item.reason}"
        )


def _write_current_dossier(paths: AppPaths, limit: int) -> None:
    config = load_config(paths.config_file)
    players = load_players(paths.players_file)
    picks = load_picks(paths.draft_file)
    metadata = load_player_metadata(paths.players_file)
    recommendations = recommend_players(
        players,
        picks,
        config.rules,
        limit=limit,
        draft_position=config.draft_position,
    )
    write_dossier(
        paths.dossier_file,
        config,
        players,
        picks,
        recommendations,
        source=str(metadata.get("source", "unknown")),
        source_updated_at=str(metadata.get("updated_at", "unknown")),
    )
    print(f"Wrote {paths.dossier_file}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    paths = AppPaths.discover()
    try:
        if args.command in {"init", "setup"}:
            created = ensure_config(paths.config_file)
            print(f"Configuration {'created' if created else 'already exists'}: {paths.config_file}")
            if args.command == "init":
                return 0
        if args.command == "configure":
            run_setup_wizard(paths)
            return 0
        if args.command == "paths":
            for label, path in (
                ("Data", paths.data_dir), ("Config", paths.config_file),
                ("Players", paths.players_file), ("Draft", paths.draft_file),
                ("Roster", paths.roster_file),
                ("Dossier", paths.dossier_file),
                ("Alert", paths.alert_file),
            ):
                print(f"{label:<8} {path}")
            return 0
        if args.command == "schedule-install":
            print(install_windows_task())
            return 0
        if args.command == "schedule-remove":
            print(remove_windows_task())
            return 0
        if args.command == "schedule-status":
            print(task_status())
            return 0
        config = load_config(paths.config_file)
        if args.command in {"refresh", "setup"} or (args.command == "alert" and args.refresh) or args.command == "scheduled-alert":
            if args.command == "refresh" and args.input:
                payload = json.loads(args.input.read_text(encoding="utf-8"))
                players = parse_players(payload, config.season)
                source = f"ESPN JSON import: {args.input.name}"
            else:
                players = fetch_players(config.season)
                source = "ESPN public fantasy API"
            save_players(paths.players_file, players, source)
            print(f"Saved {len(players)} ESPN fantasy players.")
            if args.command == "refresh":
                return 0
        if args.command == "doctor":
            checks = {
                "configuration": paths.config_file.is_file(),
                "player pool": paths.players_file.is_file(),
                "draft state": paths.draft_file.is_file() or not load_picks(paths.draft_file),
            }
            for name, passed in checks.items():
                print(f"[{'OK' if passed else 'MISSING'}] {name}")
            return 0 if all(checks.values()) else 1
        players = load_players(paths.players_file)
        picks = load_picks(paths.draft_file)
        if args.command == "board":
            _print_board(players, picks, config, args.limit)
        elif args.command == "search":
            matches = [p for p in players if args.query.casefold() in p.name.casefold()]
            for player in matches[:30]:
                print(f"{player.player_id:<10} {player.name:<28} {player.position:<4} {player.pro_team}")
        elif args.command == "pick":
            player = _find_player(players, args.player)
            if player.player_id in {pick.player_id for pick in picks}:
                raise ValueError(f"{player.name} is already drafted.")
            is_mine = args.mine or bool(config.my_team and args.team == config.my_team)
            picks.append(DraftPick(len(picks) + 1, player.player_id, args.team, is_mine))
            save_picks(paths.draft_file, picks)
            print(f"Recorded #{len(picks)}: {player.name} ({player.position}){' [MINE]' if is_mine else ''}")
            _print_board(players, picks, config, 10)
            _write_current_dossier(paths, 75)
        elif args.command == "undo":
            if not picks:
                raise ValueError("No picks to undo.")
            removed = picks.pop()
            save_picks(paths.draft_file, picks)
            print(f"Removed pick #{removed.overall}: {players_by_id(players)[removed.player_id].name}")
            _write_current_dossier(paths, 75)
        elif args.command == "reset":
            save_picks(paths.draft_file, [])
            print("Draft picks cleared.")
            _write_current_dossier(paths, 75)
        elif args.command == "dossier":
            _write_current_dossier(paths, args.limit)
        elif args.command == "email":
            if config.email is None:
                raise ValueError("Configure [email] before sending a report.")
            _write_current_dossier(paths, args.limit)
            send_email_report(paths.dossier_file, config.email, paths.secrets_file)
            print(f"Sent report to {config.email.recipient}")
        elif args.command == "roster":
            if args.from_my_picks and args.players:
                raise ValueError("Use player names or --from-my-picks, not both.")
            if args.from_my_picks:
                player_ids = [pick.player_id for pick in picks if pick.is_mine]
                if not player_ids:
                    raise ValueError("No picks are marked as mine.")
                save_roster(paths.roster_file, player_ids)
            elif args.players:
                player_ids = [_find_player(players, query).player_id for query in args.players]
                if len(set(player_ids)) != len(player_ids):
                    raise ValueError("Roster contains duplicate players.")
                save_roster(paths.roster_file, player_ids)
            else:
                player_ids = load_roster(paths.roster_file)
            by_id = players_by_id(players)
            print("Post-draft roster:")
            for player_id in player_ids:
                player = by_id.get(player_id)
                print(f"- {player.name} ({player.position}, {player.pro_team})" if player else f"- Unknown ESPN ID {player_id}")
        elif args.command == "lineup":
            player_ids = load_roster(paths.roster_file)
            if not player_ids:
                raise ValueError("Set the post-draft roster first.")
            by_id = players_by_id(players)
            roster = [by_id[player_id] for player_id in player_ids if player_id in by_id]
            recommendation = recommend_lineup(roster, config.rules)
            print("Full-season expected-points lineup (weekly projections are not yet available):")
            for item in recommendation.starters:
                print(f"{item.slot:<4} {item.player.name:<28} {item.player.projected_points:>7.1f}")
            print(f"Expected starter total: {recommendation.expected_points:.1f}")
            print("Bench: " + ", ".join(player.name for player in recommendation.bench))
            if recommendation.missing_projections:
                print("Projection unavailable: " + ", ".join(player.name for player in recommendation.missing_projections))
        elif args.command in {"alert", "scheduled-alert"}:
            roster_ids = load_roster(paths.roster_file)
            intelligence = None
            articles = []
            intelligence_warning = None
            if config.gemini.enabled:
                try:
                    by_id = players_by_id(players)
                    roster = [by_id[player_id] for player_id in roster_ids if player_id in by_id]
                    candidates = recommend_players(
                        players, picks, config.rules, limit=10, draft_position=config.draft_position
                    )
                    entities = list(dict.fromkeys(
                        [player.name for player in roster]
                        + [item.player.name for item in candidates]
                    ))
                    articles = fetch_news(entities, config.gemini.max_queries)
                    if articles:
                        intelligence = analyze_news(
                            entities,
                            articles,
                            api_key=load_api_key(paths.secrets_file),
                            model=config.gemini.model,
                            cache_file=paths.intelligence_file,
                            budget_file=paths.ai_budget_file,
                            max_articles=config.gemini.max_articles,
                            daily_request_limit=config.gemini.daily_request_limit,
                            daily_token_limit=config.gemini.daily_token_limit,
                        )
                    else:
                        intelligence_warning = "No recent player-specific injury or availability evidence was found."
                except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
                    intelligence_warning = str(error)
                    print(f"Warning: Gemini/news analysis unavailable: {error}", file=sys.stderr)
            alert_text = build_alert(
                config,
                players,
                picks,
                roster_ids,
                intelligence,
                articles,
                intelligence_warning,
            )
            paths.alert_file.write_text(alert_text, encoding="utf-8")
            print(alert_text)
            print(f"Wrote {paths.alert_file}")
            should_send = args.command == "scheduled-alert" or args.send
            if should_send and config.email is not None:
                send_email_report(paths.alert_file, config.email, paths.secrets_file)
                print(f"Sent alert to {config.email.recipient}")
            elif args.command == "scheduled-alert":
                print("Email is not configured; the alert was saved locally only.")
            elif args.send:
                raise ValueError("Configure [email] before sending an alert.")
        elif args.command == "setup":
            _write_current_dossier(paths, 75)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def players_by_id(players: list[Player]) -> dict[int, Player]:
    return {player.player_id: player for player in players}