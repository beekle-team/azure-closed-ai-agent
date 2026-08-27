from closed_agent.channels.directory import resolve_user_id
from closed_agent.channels.types import InboundMessage


def parse_mail(payload: dict) -> InboundMessage:
    """Graph のメール通知を、質問・口伝取り込み・承認に分ける。"""
    subject = str(payload.get("subject") or "").strip()
    body = str(payload.get("body") or payload.get("text") or "").strip()
    sender = str(payload.get("from") or payload.get("sender") or "").strip()
    intent = str(payload.get("intent") or _guess_intent(subject, body))
    approval_id = str(payload.get("approval_id") or _approval_id(subject, body))
    text = body or subject
    if intent == "ingest" and subject:
        text = body
    return InboundMessage(
        channel="mail",
        user_id=resolve_user_id(sender),
        text=text,
        reply_to=sender,
        intent=intent if intent in {"ask", "ingest", "approve"} else "ask",
        title=subject or "メールからの口伝",
        approval_id=approval_id,
        identity=sender,
    )


def _guess_intent(subject: str, body: str) -> str:
    hay = f"{subject} {body}"
    if "承認" in hay or "approve" in hay.lower():
        return "approve"
    if subject.startswith("口伝") or "口伝:" in hay or "取り込み" in hay:
        return "ingest"
    return "ask"


def _approval_id(subject: str, body: str) -> str:
    for part in f"{subject} {body}".split():
        if part.startswith("apr-") or part.startswith("approval:"):
            return part.split(":", 1)[-1]
    return ""
