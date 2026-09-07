from __future__ import annotations

import getpass
from pathlib import Path

from .paths import AppPaths


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
    season = _number("NFL season", 2026, 2026)
    teams = _number("Number of fantasy teams", 14, 2)
    scoring = _ask("Scoring (ppr, half, or standard)", "ppr").lower()
    while scoring not in {"ppr", "half", "standard"}:
        scoring = _ask("Please enter ppr, half, or standard", "ppr").lower()
    draft_position = _number("Draft position (0 until ESPN assigns it)", 0)
    while draft_position > teams:
        print(f"Draft position cannot exceed {teams}.")
        draft_position = _number("Draft position", 0)

    configure_email = _ask("Configure manual email reports? (y/n)", "n").lower() == "y"
    email_lines = [
        "[email]",
        'smtp_host = ""',
        "smtp_port = 587",
        "starttls = true",
        'sender = ""',
        'recipient = ""',
        'subject = "NFL fantasy draft board"',
    ]
    if configure_email:
        host = _ask("SMTP host (for Gmail: smtp.gmail.com)", "smtp.gmail.com")
        port = _number("SMTP port", 587, 1)
        sender = input("Sender email address: ").strip()
        recipient = input("Recipient email address: ").strip()
        username = _ask("SMTP username", sender)
        password = getpass.getpass("SMTP app password: ")
        if not sender or not recipient or not username or not password:
            raise ValueError("Email setup requires sender, recipient, username, and app password.")
        email_lines = [
            "[email]",
            f'smtp_host = "{host}"',
            f"smtp_port = {port}",
            "starttls = true",
            f'sender = "{sender}"',
            f'recipient = "{recipient}"',
            'subject = "NFL fantasy draft board"',
        ]
        paths.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        paths.secrets_file.write_text(
            f"NFLFANTASY_SMTP_USERNAME={username}\nNFLFANTASY_SMTP_PASSWORD={password}\n",
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
        ]
    )
    paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    paths.config_file.write_text(config, encoding="utf-8")
    print(f"Configuration saved to {paths.config_file}")