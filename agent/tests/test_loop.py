from closed_agent.orchestrator import _citations, _needs_approval
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.schemas import Citation


def test_needs_approval_for_send() -> None:
    assert _needs_approval("この見積を顧客へ送信して")
    assert not _needs_approval("見積作成手順は誰が使うか")


def test_citations_deduplicate() -> None:
    hits = [
        RetrievalHit("情報取扱規程", "Policy", "GOVERNS 見積作成手順", "graph"),
        RetrievalHit("情報取扱規程", "Policy", "GOVERNS 社内CRM", "graph"),
    ]
    citations = _citations(hits)
    assert citations == [
        Citation(name="情報取扱規程", kind="Policy", reason="GOVERNS 見積作成手順", source="graph"),
    ]
