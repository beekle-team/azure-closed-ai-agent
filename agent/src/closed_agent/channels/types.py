from dataclasses import dataclass
from typing import Literal


@dataclass
class InboundMessage:
    channel: Literal["web", "teams", "mail"]
    user_id: int
    text: str
    reply_to: str = ""
    intent: Literal["ask", "ingest", "approve"] = "ask"
    title: str = ""
    approval_id: str = ""


@dataclass
class ChannelReply:
    channel: str
    to: str
    text: str
    would_send: str
