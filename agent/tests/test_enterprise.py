from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from closed_agent.acl import can_read, classify
from closed_agent.approvals import ApprovalStore
from closed_agent.audit import AuditLog
from closed_agent.dlp import scan
from closed_agent.graph.client import GraphClient
from closed_agent.identity import directory
from closed_agent.main import app
from closed_agent.orchestrator import run_chat
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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unknown_identity_is_nobody() -> None:
    assert directory.resolve_identity("outsider@evil.example") is None
    assert directory.resolve_identity("aad-admin") is not None


def test_sales_cannot_read_credit_tacit() -> None:
    sales = directory.resolve_identity("sales@example.com")
    assert sales is not None
    assert not can_read(sales, classify("口伝-与信ルート", "TacitKnowledge"))
    assert can_read(sales, classify("稟議運用", "Document"))
    assert can_read(sales, classify("口伝-大型稟議", "TacitKnowledge"))


def test_hr_cannot_read_contract_insurance() -> None:
    hr = directory.resolve_identity("hr@example.com")
    assert hr is not None
    assert not can_read(hr, classify("口伝-出張保険", "TacitKnowledge"))
    assert can_read(hr, classify("出張マニュアル", "Document"))


def test_dlp_blocks_contract_article() -> None:
    assert scan("本契約の定め 第1条 甲及び乙").blocked
    assert not scan("海外出張の保険は誰が見るか").blocked


@pytest.mark.asyncio
async def test_sales_chat_hides_credit_room(tmp_path: Path) -> None:
    sales = directory.resolve_identity("sales@example.com")
    assert sales is not None
    response = await run_chat(
        sales.user_id,
        "初めての取引先の与信ルートは？",
        facade=_facade(),
        principal=sales,
        approvals=ApprovalStore(tmp_path / "a.json"),
        audit=AuditLog(tmp_path / "audit.jsonl"),
    )
    names = " ".join(cite.name for cite in response.citations)
    assert "口伝-与信ルート" not in names
    assert "Outlook 与信室" not in names
    assert "近藤" not in names


@pytest.mark.asyncio
async def test_unknown_user_is_forbidden(tmp_path: Path) -> None:
    response = await run_chat(
        99,
        "与信ルートは？",
        facade=_facade(),
        approvals=ApprovalStore(tmp_path / "a.json"),
        audit=AuditLog(tmp_path / "audit.jsonl"),
    )
    assert response.status == "forbidden"


@pytest.mark.asyncio
async def test_approval_persists_and_executes(tmp_path: Path) -> None:
    admin = directory.by_user_id(1)
    assert admin is not None
    store = ApprovalStore(tmp_path / "a.json")
    log = AuditLog(tmp_path / "audit.jsonl")
    pending = await run_chat(
        1,
        "契約レビュー依頼を法務に送信して",
        facade=_facade(),
        principal=admin,
        approvals=store,
        audit=log,
    )
    assert pending.status == "needs_approval"
    assert store.get(pending.approval_id or "") is not None
    decided = store.decide(pending.approval_id or "", principal=admin, approved=True)
    assert decided is not None
    assert decided.status == "approved"
    resumed = await run_chat(
        1,
        "契約レビュー依頼を法務に送信して",
        facade=_facade(),
        principal=admin,
        approval_id=pending.approval_id,
        approvals=store,
        audit=log,
    )
    assert resumed.status in {"answered", "needs_approval", "skill_ran"}
    assert log.intact()


def test_http_requires_token() -> None:
    client = TestClient(app)
    assert client.get("/v1/knowledge").status_code == 401
    assert client.post("/v1/chat", json={"question": "稟議は？"}).status_code == 401
    assert client.post("/v1/ingest", json={"path": "x.md", "title": "x", "body": "y", "kind": "tacit"}).status_code == 401


def test_http_rejects_unknown_token() -> None:
    client = TestClient(app)
    assert client.get("/v1/knowledge", headers=_headers("no-such-token")).status_code == 401


def test_http_fake_approval_is_404() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/approvals/does-not-exist",
        headers=_headers("local-admin"),
        json={"approved": True},
    )
    assert response.status_code == 404


def test_sales_knowledge_omits_credit() -> None:
    client = TestClient(app)
    items = client.get("/v1/knowledge", headers=_headers("local-sales")).json()
    names = {item["name"] for item in items}
    assert "口伝-与信ルート" not in names
    assert "Outlook 与信室からの注意" not in names
    assert "稟議運用" in names


def test_admin_sees_credit() -> None:
    client = TestClient(app)
    items = client.get("/v1/knowledge", headers=_headers("local-admin")).json()
    names = {item["name"] for item in items}
    assert "口伝-与信ルート" in names


def test_sales_cannot_run_credit_skill() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/skills/credit-check/run",
        headers=_headers("local-sales"),
        json={"inputs": {}},
    )
    assert response.status_code == 403


def test_sales_cannot_self_approve() -> None:
    client = TestClient(app)
    pending = client.post(
        "/v1/chat",
        headers=_headers("local-sales"),
        json={"question": "この見積を顧客へ送信して"},
    ).json()
    assert pending["status"] == "needs_approval"
    denied = client.post(
        f"/v1/approvals/{pending['approval_id']}",
        headers=_headers("local-sales"),
        json={"approved": True},
    )
    assert denied.status_code == 403


def test_dlp_blocks_http_ingest() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/ingest",
        headers=_headers("local-admin"),
        json={
            "path": "secret.md",
            "title": "契約",
            "body": "第1条 甲及び乙は本契約の定めに従う。",
            "kind": "tacit",
        },
    )
    assert response.status_code == 422


def test_me_and_audit() -> None:
    client = TestClient(app)
    me = client.get("/v1/me", headers=_headers("local-admin")).json()
    assert me["department"] == "情報システム部"
    assert me["can_audit"] is True
    audit = client.get("/v1/audit", headers=_headers("local-admin")).json()
    assert audit["intact"] is True
    sales_audit = client.get("/v1/audit", headers=_headers("local-sales"))
    assert sales_audit.status_code == 403
