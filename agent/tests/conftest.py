import pytest

from closed_agent.approvals import approval_store
from closed_agent.audit import audit_log
from closed_agent.conversations import conversation_store


@pytest.fixture(autouse=True)
def isolate_control_plane() -> None:
    """手元の承認・監査・会話が、前のプロセスの残りで試験を汚さないようにする。"""
    approval_store.reset()
    audit_log.reset()
    conversation_store.reset()
