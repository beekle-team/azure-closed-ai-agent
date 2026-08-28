from closed_agent.orchestrator import _citations, _evidence_line, _needs_approval
from closed_agent.retrieve.types import RetrievalHit
from closed_agent.schemas import Citation


def test_needs_approval_for_send() -> None:
    assert _needs_approval("この見積を顧客へ送信して")
    assert _needs_approval("見積をメールを出して")
    assert not _needs_approval("見積作成手順は誰が使うか")


def test_evidence_line_prefers_body_text() -> None:
    hit = RetrievalHit(
        "口伝-出張保険",
        "TacitKnowledge",
        "出張、保険",
        "search",
        text="海外出張の保険は、申請画面に項目が無い。契約管理部が包括契約を持っている。",
    )
    line = _evidence_line(hit)
    assert "契約管理部" in line
    assert "申請画面に項目が無い" in line


def test_citations_deduplicate() -> None:
    hits = [
        RetrievalHit("情報取扱規程", "Policy", "GOVERNS 見積作成手順", "graph"),
        RetrievalHit("情報取扱規程", "Policy", "GOVERNS 社内CRM", "graph"),
    ]
    citations = _citations(hits)
    assert citations == [
        Citation(name="情報取扱規程", kind="Policy", reason="GOVERNS 見積作成手順", source="graph"),
    ]
