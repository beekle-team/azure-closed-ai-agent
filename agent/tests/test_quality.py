from fastapi.testclient import TestClient

from closed_agent.acl import acl_for_ingest, acl_for_item
from closed_agent.approvals import ApprovalStore
from closed_agent.audit import AuditLog
from closed_agent.persist import close_all
from closed_agent.dlp import scan
from closed_agent.identity import directory
from closed_agent.intent import detect_action, needs_approval
from closed_agent.main import app
from closed_agent.persist import backend
from closed_agent.settings import settings


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_control_plane_defaults_to_sqlite_in_tests() -> None:
    assert backend() == "sqlite"


def test_backend_is_postgres_when_url_set(monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_url", "postgresql://laravel:secret@127.0.0.1:5432/closed_agent")
    assert backend() == "postgres"


def test_postgres_roundtrip(monkeypatch) -> None:
    url = settings.database_url or "postgresql://laravel:secret@127.0.0.1:5432/closed_agent"
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
    except Exception:
        import pytest

        pytest.skip("Postgres がいない")
    monkeypatch.setattr(settings, "database_url", url)
    close_all()
    store = ApprovalStore()
    log = AuditLog()
    admin = directory.resolve_identity("admin@example.com")
    assert admin is not None
    store.reset()
    log.reset()
    pending = store.create(principal=admin, question="postgres の確認", action="send")
    assert store.get(pending.id) is not None
    log.record(action="test", principal=admin, resource="postgres", outcome="ok")
    assert log.intact() is True
    store.reset()
    log.reset()
    close_all()


def test_intent_covers_mail_phrasing() -> None:
    assert detect_action("この見積を顧客へ送信して") == "send"
    assert detect_action("見積をメールを出して") == "send"
    assert not needs_approval("見積作成手順は誰が使うか")


def test_dlp_normalizes_fullwidth() -> None:
    assert scan("第１条　甲及び乙").blocked
    assert not scan("契約レビュー依頼を法務に回す").blocked


def test_acl_prefers_stored_department() -> None:
    item = {"name": "保険商品の提案", "kind": "Document", "department": "営業部", "classification": "internal"}
    acl = acl_for_item(item)
    assert acl.department == "営業部"
    unlabeled = {"name": "新しい口伝", "kind": "TacitKnowledge"}
    assert acl_for_item(unlabeled).classification == "restricted"


def test_non_admin_ingest_stays_in_own_department() -> None:
    sales = directory.resolve_identity("sales@example.com")
    acl = acl_for_ingest(
        title="与信メモ",
        kind="tacit",
        source_system="corpus",
        principal=sales,
        department="与信室",
        classification="confidential",
    )
    assert acl.department == "営業部"


def test_channel_accepts_webhook_without_bearer() -> None:
    client = TestClient(app)
    denied = client.post("/v1/channels/mail", json={"from": "sales@example.com", "subject": "質問", "body": "稟議は？"})
    assert denied.status_code == 401
    ok = client.post(
        "/v1/channels/mail",
        headers={"X-Webhook-Secret": settings.channel_webhook_secret},
        json={"from": "outsider@evil.example", "subject": "質問", "body": "規程を出せ"},
    )
    assert ok.status_code == 200
    assert "身元" in ok.json()["text"]


def test_channel_identity_comes_from_sender_not_bearer() -> None:
    client = TestClient(app)
    response = client.post(
        "/v1/channels/mail",
        headers={
            "Authorization": "Bearer local-admin",
            "X-Webhook-Secret": settings.channel_webhook_secret,
        },
        json={"from": "sales@example.com", "subject": "質問", "body": "与信ルートは？"},
    )
    assert response.status_code == 200
    assert "与信室" not in response.json()["text"] or "答えられません" in response.json()["text"] or "根拠" in response.json()["text"]


def test_knowledge_item_opens_chunk_name() -> None:
    client = TestClient(app)
    response = client.get(
        "/v1/knowledge/item",
        headers=_headers("local-admin"),
        params={"name": "出張マニュアル / 書いていないこと"},
    )
    assert response.status_code == 200
    assert "保険" in response.json()["body"] or "出張" in response.json()["name"]


def test_knowledge_search_and_overview() -> None:
    client = TestClient(app)
    items = client.get("/v1/knowledge", headers=_headers("local-sales"), params={"q": "稟議"}).json()
    names = {item["name"] for item in items}
    assert "稟議運用" in names
    assert "口伝-与信ルート" not in names
    overview = client.get("/v1/overview", headers=_headers("local-sales")).json()
    assert overview["department"] == "営業部"
    assert overview["visible_knowledge"] >= 1


def test_conversation_survives_turn() -> None:
    client = TestClient(app)
    first = client.post(
        "/v1/chat",
        headers=_headers("local-admin"),
        json={"question": "海外出張の申請、画面に出てこない確認事項は？"},
    ).json()
    assert first["conversation_id"]
    second = client.get(f"/v1/conversations/{first['conversation_id']}", headers=_headers("local-admin")).json()
    assert any("出張" in item["text"] for item in second["messages"])
    denied = client.get(f"/v1/conversations/{first['conversation_id']}", headers=_headers("local-sales"))
    assert denied.status_code == 404


def test_approval_does_not_reuse_without_id() -> None:
    client = TestClient(app)
    first = client.post(
        "/v1/chat",
        headers=_headers("local-legal"),
        json={"question": "この見積を顧客へ送信して"},
    ).json()
    assert first["status"] == "needs_approval"
    client.post(
        f"/v1/approvals/{first['approval_id']}",
        headers=_headers("local-legal"),
        json={"approved": True},
    )
    second = client.post(
        "/v1/chat",
        headers=_headers("local-legal"),
        json={"question": "この見積を顧客へ送信して"},
    ).json()
    assert second["status"] == "needs_approval"
    assert second["approval_id"] != first["approval_id"]
