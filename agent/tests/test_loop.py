from closed_agent.agent.loop import _citations, _needs_approval
from closed_agent.schemas import Citation


def test_needs_approval_for_send() -> None:
    assert _needs_approval("この見積を顧客へ送信して")
    assert not _needs_approval("見積作成手順は誰が使うか")


def test_citations_deduplicate() -> None:
    rows = [
        {"name": "情報取扱規程", "kind": "Policy", "relation": "GOVERNS", "neighbor": "見積作成手順"},
        {"name": "情報取扱規程", "kind": "Policy", "relation": "GOVERNS", "neighbor": "社内CRM"},
    ]
    citations = _citations(rows)
    assert citations == [
        Citation(name="情報取扱規程", kind="Policy", reason="GOVERNS 見積作成手順"),
    ]
