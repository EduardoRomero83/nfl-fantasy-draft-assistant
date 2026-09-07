from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import EmailConfig


def send_email_report(path: Path, settings: EmailConfig) -> None:
    if not path.is_file():
        raise ValueError(f"Report does not exist: {path}")
    if (
        "@" not in settings.recipient
        or settings.recipient.startswith("@")
        or settings.recipient.endswith("@")
    ):
        raise ValueError("Email recipient must be a valid email address.")
    report_kind = (
        "Thursday lineup alert" if path.suffix.lower() == ".txt" else "draft board"
    )
    payload = json.dumps(
        {
            "sender": settings.recipient,
            "recipient": settings.recipient,
            "subject": settings.subject,
            "body": f"The current NFL fantasy {report_kind} is attached.",
            "attachment": str(path.resolve()),
        },
        ensure_ascii=False,
    )
    script = """
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
$payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
$outlook = $null
$mail = $null
$sendAccount = $null
try {
    $outlook = New-Object -ComObject Outlook.Application
    foreach ($account in $outlook.Session.Accounts) {
        if ([string]::Equals(
            [string]$account.SmtpAddress,
            [string]$payload.sender,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            $sendAccount = $account
            break
        }
    }
    if ($sendAccount -eq $null) {
        throw "Classic Outlook has no signed-in account matching $($payload.sender)."
    }
    $mail = $outlook.CreateItem(0)
    $mail.SendUsingAccount = $sendAccount
    $mail.To = $payload.recipient
    $mail.Subject = $payload.subject
    $mail.Body = $payload.body
    [void]$mail.Attachments.Add([string]$payload.attachment)
    $mail.Send()
}
finally {
    if ($mail -ne $null) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($mail)
    }
    if ($sendAccount -ne $null) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($sendAccount)
    }
    if ($outlook -ne $null) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($outlook)
    }
}
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            "Classic Outlook did not complete the email send within 60 seconds."
        ) from error
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Outlook email send failed."
        )