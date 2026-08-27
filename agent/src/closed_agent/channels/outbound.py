from __future__ import annotations

import smtplib
from email.message import EmailMessage

import httpx

from closed_agent.settings import settings

OUTBOX: list[dict[str, str]] = []


def send_mail(*, to: str, subject: str, body: str) -> dict[str, str]:
    record = {
        "from": settings.mail_from,
        "to": to,
        "subject": subject,
        "body": body,
        "via": "outbox",
    }
    if settings.mailpit_url.strip():
        try:
            response = httpx.post(
                settings.mailpit_url.rstrip("/") + "/api/v1/send",
                json={
                    "From": {"Email": settings.mail_from},
                    "To": [{"Email": to}],
                    "Subject": subject,
                    "Text": body,
                },
                timeout=8.0,
            )
            response.raise_for_status()
            record["via"] = "mailpit"
        except httpx.HTTPError:
            record["via"] = "outbox"
    elif settings.smtp_host.strip():
        message = EmailMessage()
        message["From"] = settings.mail_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8) as client:
            client.send_message(message)
        record["via"] = "smtp"
    OUTBOX.append(record)
    return record


def list_inbox() -> list[dict[str, str]]:
    if not settings.mailpit_url.strip():
        return []
    try:
        response = httpx.get(settings.mailpit_url.rstrip("/") + "/api/v1/messages", timeout=8.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    messages = []
    for item in response.json().get("messages", []):
        messages.append(
            {
                "id": str(item.get("ID") or ""),
                "from": str((item.get("From") or {}).get("Address") or ""),
                "to": ", ".join(addr.get("Address") or "" for addr in item.get("To") or []),
                "subject": str(item.get("Subject") or ""),
                "created": str(item.get("Created") or ""),
            }
        )
    return messages
