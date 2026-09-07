from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    config_file: Path
    secrets_file: Path
    players_file: Path
    draft_file: Path
    roster_file: Path
    dossier_file: Path
    alert_file: Path
    logs_dir: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise RuntimeError("LOCALAPPDATA is required on Windows.")
        data_dir = Path(local) / "NFLFantasyDraftAssistant"
        return cls(
            data_dir=data_dir,
            config_file=data_dir / "config.toml",
            secrets_file=data_dir / "secrets.env",
            players_file=data_dir / "players.json",
            draft_file=data_dir / "draft.json",
            roster_file=data_dir / "roster.json",
            dossier_file=data_dir / "draft-room-context.md",
            alert_file=data_dir / "latest-alert.txt",
            logs_dir=data_dir / "logs",
        )