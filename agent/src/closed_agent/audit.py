from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from closed_agent.identity import Principal
from closed_agent.persist import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    """改ざん検知用に前件ハッシュを繋いだ追記ログ。正本は Postgres。試験と手元だけ SQLite。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = Lock()
        connect(path)

    def _db(self):
        return connect(self.path)

    def _tail_hash(self) -> str:
        row = self._db().execute("SELECT hash FROM ca_audit ORDER BY id DESC LIMIT 1").fetchone()
        return row["hash"] if row else "genesis"

    def record(
        self,
        *,
        action: str,
        principal: Principal | None,
        resource: str,
        outcome: str,
        detail: str = "",
        channel: str = "api",
    ) -> dict[str, str]:
        with self._lock:
            event = {
                "ts": _now(),
                "action": action,
                "actor": principal.email if principal else "anonymous",
                "user_id": str(principal.user_id) if principal else "",
                "department": principal.department if principal else "",
                "resource": resource,
                "outcome": outcome,
                "detail": (detail or "")[:500],
                "channel": channel,
                "prev_hash": self._tail_hash(),
            }
            payload = json.dumps(event, ensure_ascii=False, sort_keys=True)
            event["hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            self._db().execute(
                """INSERT INTO ca_audit
                   (ts, action, actor, user_id, department, resource, outcome, detail, channel, prev_hash, hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["ts"],
                    event["action"],
                    event["actor"],
                    event["user_id"],
                    event["department"],
                    event["resource"],
                    event["outcome"],
                    event["detail"],
                    event["channel"],
                    event["prev_hash"],
                    event["hash"],
                ),
            )
            self._db().commit()
        return event

    def list(self, limit: int = 100, department: str | None = None) -> list[dict[str, str]]:
        if department:
            rows = self._db().execute(
                "SELECT * FROM ca_audit WHERE department = ? ORDER BY id DESC LIMIT ?",
                (department, limit),
            ).fetchall()
        else:
            rows = self._db().execute("SELECT * FROM ca_audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        items = []
        for row in reversed(rows):
            items.append(
                {
                    "ts": row["ts"],
                    "action": row["action"],
                    "actor": row["actor"],
                    "user_id": row["user_id"],
                    "department": row["department"],
                    "resource": row["resource"],
                    "outcome": row["outcome"],
                    "detail": row["detail"],
                    "channel": row["channel"],
                    "prev_hash": row["prev_hash"],
                    "hash": row["hash"],
                }
            )
        return items

    def reset(self) -> None:
        with self._lock:
            self._db().execute("DELETE FROM ca_audit")
            self._db().commit()

    def intact(self) -> bool:
        prev = "genesis"
        rows = self._db().execute(
            "SELECT ts, action, actor, user_id, department, resource, outcome, detail, channel, prev_hash, hash FROM ca_audit ORDER BY id"
        ).fetchall()
        for row in rows:
            event = {
                "ts": row["ts"],
                "action": row["action"],
                "actor": row["actor"],
                "user_id": row["user_id"],
                "department": row["department"],
                "resource": row["resource"],
                "outcome": row["outcome"],
                "detail": row["detail"],
                "channel": row["channel"],
                "prev_hash": row["prev_hash"],
            }
            if event["prev_hash"] != prev:
                return False
            digest = hashlib.sha256(json.dumps(event, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            if digest != row["hash"]:
                return False
            prev = row["hash"]
        return True


audit_log = AuditLog()
