from closed_agent.channels.directory import resolve_user_id
from closed_agent.channels.types import InboundMessage


def parse_teams(payload: dict) -> InboundMessage:
    """Bot Framework の activity を、orchestrator 向けに薄くする。"""
    text = str(payload.get("text") or payload.get("message") or "").strip()
    sender = payload.get("from") or {}
    identity = str(payload.get("user_id") or sender.get("aadObjectId") or sender.get("id") or "")
    conversation = payload.get("conversation") or {}
    reply_to = str(conversation.get("id") or payload.get("reply_to") or identity)
    return InboundMessage(
        channel="teams",
        user_id=resolve_user_id(identity),
        text=text,
        reply_to=reply_to,
        intent="ask",
    )
