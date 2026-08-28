from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from closed_agent.identity import Principal
from closed_agent.persist import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = Lock()
        connect(path)

    def _db(self):
        return connect(self.path)

    def start(self, principal: Principal) -> str:
        conversation_id = str(uuid4())
        now = _now()
        with self._lock:
            self._db().execute(
                "INSERT INTO ca_conversations (id, user_id, department, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, principal.user_id, principal.department, now, now),
            )
            self._db().commit()
        return conversation_id

    def get(self, conversation_id: str, principal: Principal) -> dict[str, object] | None:
        row = self._db().execute("SELECT * FROM ca_conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        if row["user_id"] != principal.user_id and not principal.is_admin:
            return None
        messages = self.history(conversation_id, limit=40)
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "department": row["department"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": messages,
        }

    def append(
        self,
        conversation_id: str,
        *,
        role: str,
        text: str,
        status: str = "",
        approval_id: str = "",
    ) -> None:
        with self._lock:
            db = self._db()
            db.execute(
                "INSERT INTO ca_messages (conversation_id, role, text, status, approval_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, role, text, status, approval_id, _now()),
            )
            db.execute("UPDATE ca_conversations SET updated_at = ? WHERE id = ?", (_now(), conversation_id))
            db.commit()

    def history(self, conversation_id: str, limit: int = 8) -> list[dict[str, str]]:
        rows = self._db().execute(
            "SELECT role, text, status, approval_id, created_at FROM ca_messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        ).fetchall()
        items = [
            {
                "role": row["role"],
                "text": row["text"],
                "status": row["status"],
                "approval_id": row["approval_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        items.reverse()
        return items

    def reset(self) -> None:
        with self._lock:
            db = self._db()
            db.execute("DELETE FROM ca_messages")
            db.execute("DELETE FROM ca_conversations")
            db.commit()


conversation_store = ConversationStore()
