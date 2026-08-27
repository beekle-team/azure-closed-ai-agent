from fastapi.testclient import TestClient

from closed_agent.channels.outbound import OUTBOX
from closed_agent.main import app


def test_console_page() -> None:
    client = TestClient(app)
    response = client.get("/app")
    assert response.status_code == 200
    assert "閉域AIエージェント" in response.text
    assert "ナレッジ" in response.text


def test_knowledge_lists_corpus_and_microsoft() -> None:
    client = TestClient(app)
    items = client.get("/v1/knowledge").json()
    names = {item["name"] for item in items}
    systems = {item["source_system"] for item in items}
    assert any("出張" in name or "口伝" in name for name in names)
    assert "sharepoint" in systems


def test_mail_send_keeps_outbox() -> None:
    OUTBOX.clear()
    client = TestClient(app)
    response = client.post(
        "/v1/mail/send",
        json={"sender": "admin@example.com", "subject": "口伝: 締日", "body": "画面より半日早い。"},
    )
    assert response.status_code == 200
    assert "出した" in response.json()["would_send"]
    assert any("締日" in item["subject"] for item in client.get("/v1/mail/outbox").json())
