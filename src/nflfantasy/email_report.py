from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import EmailConfig


def _credentials(secrets_path: Path | None) -> tuple[str, str]:
    username = os.environ.get("NFLFANTASY_SMTP_USERNAME", "")
    password = os.environ.get("NFLFANTASY_SMTP_PASSWORD", "")
    if secrets_path is not None and secrets_path.is_file():
        values = {}
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key.strip()] = value.strip()
        username = username or values.get("NFLFANTASY_SMTP_USERNAME", "")
        password = password or values.get("NFLFANTASY_SMTP_PASSWORD", "")
    return username, password


def send_email_report(
    path: Path, settings: EmailConfig, secrets_path: Path | None = None
) -> None:
    username, password = _credentials(secrets_path)
    if not username or not password:
        raise ValueError(
            "Run SETUP.cmd again to configure email credentials."
        )
    if not path.is_file():
        raise ValueError(f"Report does not exist: {path}")

    message = EmailMessage()
    message["Subject"] = settings.subject
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message.set_content(
        "The current NFL fantasy draft board is attached. This report was sent manually; "
        "no recurring alert schedule is configured."
    )
    message.add_attachment(
        path.read_text(encoding="utf-8"),
        subtype="markdown",
        filename=path.name,
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as client:
        if settings.starttls:
            client.starttls()
        client.login(username, password)
        client.send_message(message)