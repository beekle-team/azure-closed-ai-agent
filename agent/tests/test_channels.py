import pytest

from closed_agent.channels.dispatch import dispatch
from closed_agent.channels.mail import parse_mail
from closed_agent.channels.teams import parse_teams
from closed_agent.graph.client import GraphClient
from closed_agent.retrieve.facade import RetrievalFacade
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.structured import StructuredStore
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog


class SilentGraph(GraphClient):
    def __init__(self) -> None:
        return

    def related(self, question: str, limit: int = 8) -> list[RetrievalHit]:
        return []

    def upsert_document(self, name: str, kind: str) -> None:
        return

    def close(self) -> None:
        return


def _facade() -> RetrievalFacade:
    return RetrievalFacade(
        graph=SilentGraph(),
        keyword=KeywordIndex(settings.sample_root / "corpus"),
        structured=StructuredStore(settings.sample_root / "structured.json"),
        skills=SkillCatalog(settings.sample_root / "skills"),
    )


def test_parse_teams_activity() -> None:
    message = parse_teams(
        {
            "type": "message",
            "text": "出張事前チェックを回して",
            "from": {"id": "aad-admin", "name": "Admin"},
            "conversation": {"id": "19:abc"},
        }
    )
    assert message.channel == "teams"
    assert message.user_id == 1
    assert message.reply_to == "19:abc"


def test_parse_mail_ingest() -> None:
    message = parse_mail(
        {
            "from": "admin@example.com",
            "subject": "口伝: 経理の締日",
            "body": "画面より半日早い。",
        }
    )
    assert message.intent == "ingest"
    assert message.title.startswith("口伝")


@pytest.mark.asyncio
async def test_teams_runs_same_skill() -> None:
    message = parse_teams({"text": "出張事前チェックを回して", "from": {"id": "1"}})
    reply = await dispatch(message, facade=_facade())
    assert "契約管理部" in reply.text
    assert reply.channel == "teams"
    assert "Teams" in reply.would_send
