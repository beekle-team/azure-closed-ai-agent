import pytest

from pathlib import Path

from closed_agent.graph.client import GraphClient
from closed_agent.orchestrator import run_chat
from closed_agent.retrieve.facade import RetrievalFacade
from closed_agent.retrieve.keyword import KeywordIndex
from closed_agent.retrieve.structured import StructuredStore
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.settings import settings
from closed_agent.skills.catalog import SkillCatalog


class SilentGraph(GraphClient):
    def __init__(self) -> None:  # noqa: D107
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


@pytest.mark.asyncio
async def test_run_skill_from_chat() -> None:
    response = await run_chat(1, "出張事前チェックを回して", facade=_facade())
    assert response.status == "skill_ran"
    assert response.skill_id == "trip-precheck"
    assert "契約管理部" in response.answer


@pytest.mark.asyncio
async def test_contract_send_needs_approval() -> None:
    response = await run_chat(1, "契約レビュー依頼を法務に送信して", facade=_facade())
    assert response.status == "needs_approval"


@pytest.mark.asyncio
async def test_question_uses_corpus() -> None:
    response = await run_chat(1, "海外出張の申請、画面に出てこない確認事項は？", facade=_facade())
    assert response.status == "answered"
    assert response.plan
    assert any("保険" in cite.name or "保険" in cite.reason or "口伝" in cite.name for cite in response.citations)
    assert response.intent == "tacit_lookup"


@pytest.mark.asyncio
async def test_cannot_answer_without_corpus(tmp_path: Path) -> None:
    facade = RetrievalFacade(
        graph=SilentGraph(),
        keyword=KeywordIndex(tmp_path / "empty-corpus"),
        structured=StructuredStore(tmp_path / "missing.json"),
        skills=SkillCatalog(tmp_path / "empty-skills"),
    )
    response = await run_chat(1, "未知の手続きは誰が決める？", facade=facade)
    assert response.status == "cannot_answer"
    assert "any_evidence" in response.missing_evidence
