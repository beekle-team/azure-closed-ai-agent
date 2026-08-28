import pytest

from closed_agent.approvals import approval_store
from closed_agent.audit import audit_log
from closed_agent.conversations import conversation_store
from closed_agent.persist import close_all
from closed_agent.settings import settings


@pytest.fixture(autouse=True)
def isolate_control_plane(monkeypatch, tmp_path) -> None:
    """試験は手元の SQLite。DATABASE_URL が付いていても本番 Postgres を触らない。"""
    monkeypatch.setattr(settings, "database_url", "")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    close_all()
    approval_store.reset()
    audit_log.reset()
    conversation_store.reset()
    yield
    close_all()
