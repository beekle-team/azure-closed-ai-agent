from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from closed_agent.identity import Principal
from closed_agent.settings import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime | None) -> str:
    return moment.isoformat() if moment else ""


@dataclass
class Approval:
    id: str
    user_id: int
    actor_email: str
    department: str
    question: str
    skill_id: str
    status: str
    created_at: str
    decided_at: str = ""
    decided_by: str = ""
    result: str = ""

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


class ApprovalStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (settings.data_dir / "approvals.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._items: dict[str, Approval] = self._load()

    def _load(self) -> dict[str, Approval]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        items: dict[str, Approval] = {}
        for item in raw:
            approval = Approval(**item)
            items[approval.id] = approval
        return items

    def _save(self) -> None:
        payload = [item.to_dict() for item in self._items.values()]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def create(self, *, principal: Principal, question: str, skill_id: str = "") -> Approval:
        approval = Approval(
            id=str(uuid4()),
            user_id=principal.user_id,
            actor_email=principal.email,
            department=principal.department,
            question=question,
            skill_id=skill_id,
            status="pending",
            created_at=_iso(_now()),
        )
        with self._lock:
            self._items[approval.id] = approval
            self._save()
        return approval

    def get(self, approval_id: str) -> Approval | None:
        return self._items.get(approval_id)

    def list(self, *, principal: Principal | None = None, status: str | None = None) -> list[Approval]:
        rows = list(self._items.values())
        if status:
            rows = [item for item in rows if item.status == status]
        if principal and not principal.is_admin and not principal.can_approve():
            rows = [item for item in rows if item.user_id == principal.user_id]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return rows

    def decide(self, approval_id: str, *, principal: Principal, approved: bool, result: str = "") -> Approval | None:
        approval = self.get(approval_id)
        if approval is None:
            return None
        if approval.status not in {"pending"}:
            return approval
        if not principal.can_approve() and principal.user_id != approval.user_id:
            return approval
        if not principal.can_approve() and approved:
            return approval
        approval.status = "approved" if approved else "rejected"
        if approved and result:
            approval.status = "executed"
            approval.result = result
        elif approved:
            approval.result = result
        approval.decided_at = _iso(_now())
        approval.decided_by = principal.email
        with self._lock:
            self._items[approval.id] = approval
            self._save()
        return approval

    def mark_executed(self, approval_id: str, result: str) -> Approval | None:
        approval = self.get(approval_id)
        if approval is None:
            return None
        approval.status = "executed"
        approval.result = result
        approval.decided_at = approval.decided_at or _iso(_now())
        with self._lock:
            self._items[approval.id] = approval
            self._save()
        return approval

    def reset(self) -> None:
        with self._lock:
            self._items = {}
            self._save()

    def usable_for(self, *, principal: Principal, question: str, skill_id: str = "") -> Approval | None:
        cutoff = _now() - timedelta(hours=1)
        for item in self._items.values():
            if item.user_id != principal.user_id:
                continue
            if item.question != question:
                continue
            if skill_id and item.skill_id and item.skill_id != skill_id:
                continue
            if item.status not in {"approved", "executed"}:
                continue
            created = datetime.fromisoformat(item.created_at)
            if created < cutoff:
                continue
            return item
        return None


approval_store = ApprovalStore()
