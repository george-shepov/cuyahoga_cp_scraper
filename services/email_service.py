"""Email delivery helper for review and approval notifications."""

from __future__ import annotations

import json
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


load_dotenv()


class EmailService:
    """Send email via SMTP when configured, otherwise write to local outbox."""

    def __init__(self):
        self.smtp_host = (os.getenv("SMTP_HOST") or "").strip() or None
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = (os.getenv("SMTP_USERNAME") or "").strip() or None
        raw_smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
        self.smtp_password = raw_smtp_password.replace(" ", "") or None
        self.smtp_from = (os.getenv("SMTP_FROM") or "").strip() or None
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in {"1", "true", "yes"}

        repo_root = Path(__file__).resolve().parent.parent
        self.outbox_path = repo_root / "logs" / "review_email_outbox.log"

    def send_email(
        self,
        *,
        to_email: Optional[str],
        subject: str,
        body: str,
    ) -> Dict[str, Any]:
        if not to_email:
            return {
                "status": "skipped",
                "reason": "missing-recipient",
            }

        if self.smtp_host and self.smtp_from:
            try:
                self._send_smtp(to_email=to_email, subject=subject, body=body)
                return {
                    "status": "sent",
                    "transport": "smtp",
                    "to": to_email,
                }
            except (smtplib.SMTPException, OSError, TimeoutError) as exc:
                # Preserve workflow continuity by falling back to local outbox.
                self._write_outbox(to_email, subject, body, error=str(exc))
                return {
                    "status": "queued-local",
                    "transport": "outbox",
                    "to": to_email,
                    "error": str(exc),
                }

        self._write_outbox(to_email, subject, body)
        return {
            "status": "queued-local",
            "transport": "outbox",
            "to": to_email,
        }

    def _send_smtp(self, *, to_email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_from
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as smtp:
            if self.smtp_use_tls:
                smtp.starttls()
            if self.smtp_username:
                smtp.login(self.smtp_username, self.smtp_password or "")
            smtp.send_message(message)

    def _write_outbox(self, to_email: str, subject: str, body: str, error: Optional[str] = None) -> None:
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "to": to_email,
            "subject": subject,
            "body": body,
            "error": error,
        }
        with self.outbox_path.open("a", encoding="utf-8") as outbox:
            outbox.write(json.dumps(event) + "\n")
