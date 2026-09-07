from __future__ import annotations

import getpass
from pathlib import Path

from .config import load_config
from .paths import AppPaths


def _read_secrets(path: Path) -> dict[str, str]:
    secrets: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                secrets[key] = value
    return secrets


def _ask(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _number(prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        answer = _ask(prompt, str(default))
        try:
            value = int(answer)
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"Enter a whole number of at least {minimum}.")


def run_setup_wizard(paths: AppPaths) -> None:
    print("NFL Fantasy Draft Assistant setup")
    print("Press Enter to accept each suggested value.")
    existing = load_config(paths.config_file) if paths.config_file.is_file() else None
    season = _number("NFL season", existing.season if existing else 2026, 2026)
    teams = _number("Number of fantasy teams", existing.rules.teams if existing else 14, 2)
    scoring = _ask("Scoring (ppr, half, or standard)", existing.rules.scoring if existing else "ppr").lower()
    while scoring not in {"ppr", "half", "standard"}:
        scoring = _ask("Please enter ppr, half, or standard", "ppr").lower()
    draft_position = _number("Draft position (0 until ESPN assigns it)", existing.draft_position if existing else 0)
    while draft_position > teams:
        print(f"Draft position cannot exceed {teams}.")
        draft_position = _number("Draft position", 0)

    secrets = _read_secrets(paths.secrets_file)
    secrets.pop("NFLFANTASY_SMTP_USERNAME", None)
    secrets.pop("NFLFANTASY_SMTP_PASSWORD", None)
    configure_email = _ask("Configure Thursday email alerts? (y/n)", "y").lower() == "y"
    email_lines = [
        "[email]",
        'recipient = ""',
        'subject = "NFL fantasy Thursday alert"',
    ]
    if configure_email:
        previous_email = existing.email if existing else None
        recipient = _ask("Recipient email address", previous_email.recipient if previous_email else "")
        if "@" not in recipient or recipient.startswith("@") or recipient.endswith("@"):
            raise ValueError("Email setup requires a valid recipient address.")
        email_lines = [
            "[email]",
            f'recipient = "{recipient}"',
            'subject = "NFL fantasy Thursday alert"',
        ]
    configure_gemini = _ask("Add Gemini injury and start-likelihood analysis? (y/n)", "y").lower() == "y"
    if configure_gemini:
        api_key = getpass.getpass(
            "Gemini API key (the same key used by UCL is allowed; input is hidden): "
        ).strip()
        if not api_key and "GEMINI_API_KEY" not in secrets:
            raise ValueError("Gemini setup requires an API key.")
        if api_key:
            secrets["GEMINI_API_KEY"] = api_key
    if secrets or paths.secrets_file.is_file():
        paths.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        paths.secrets_file.write_text(
            "".join(f"{key}={value}\n" for key, value in secrets.items()),
            encoding="utf-8",
        )

    config = "\n".join(
        [
            f"season = {season}",
            f"teams = {teams}",
            f'scoring = "{scoring}"',
            'matchup = "head_to_head"',
            'draft_type = "snake"',
            "my_team = 0",
            f"draft_position = {draft_position}",
            "",
            "[roster]",
            "QB = 1",
            "RB = 2",
            "WR = 2",
            "TE = 1",
            "FLEX = 1",
            "K = 1",
            "BE = 7",
            '"D/ST" = 1',
            "",
            *email_lines,
            "",
            "[gemini]",
            f"enabled = {'true' if configure_gemini else 'false'}",
            'model = "gemini-2.5-flash"',
            "max_queries = 4",
            "max_articles = 12",
            "daily_request_limit = 2",
            "daily_token_limit = 20000",
            "",
        ]
    )
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text(config, encoding="utf-8")
    print(f"Configuration saved to {paths.config_file}")