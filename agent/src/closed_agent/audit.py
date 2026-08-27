from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from closed_agent.identity import Principal
from closed_agent.settings import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    """改ざん検知用に前件ハッシュを繋いだ追記ログ。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (settings.data_dir / "audit.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._last_hash = self._tail_hash()

    def _tail_hash(self) -> str:
        if not self.path.exists():
            return "genesis"
        last = "genesis"
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                last = json.loads(line).get("hash") or last
            except json.JSONDecodeError:
                continue
        return last

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
                "prev_hash": self._last_hash,
            }
            payload = json.dumps(event, ensure_ascii=False, sort_keys=True)
            event["hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._last_hash = event["hash"]
        return event

    def list(self, limit: int = 100, department: str | None = None) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, str]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if department and item.get("department") != department:
                continue
            rows.append(item)
        return rows[-limit:]

    def reset(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
            self._last_hash = "genesis"

    def intact(self) -> bool:
        prev = "genesis"
        if not self.path.exists():
            return True
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                return False
            expected_prev = item.get("prev_hash")
            if expected_prev != prev:
                return False
            copy = {key: value for key, value in item.items() if key != "hash"}
            digest = hashlib.sha256(
                json.dumps(copy, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if digest != item.get("hash"):
                return False
            prev = item["hash"]
        return True


audit_log = AuditLog()
