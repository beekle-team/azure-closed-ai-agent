from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from closed_agent.identity import Principal
from closed_agent.persist import connect


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
    action: str = ""

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _from_row(row) -> Approval:
    keys = row.keys()
    return Approval(
        id=row["id"],
        user_id=int(row["user_id"]),
        actor_email=row["actor_email"],
        department=row["department"],
        question=row["question"],
        skill_id=row["skill_id"] or "",
        status=row["status"],
        created_at=row["created_at"],
        decided_at=row["decided_at"] or "",
        decided_by=row["decided_by"] or "",
        result=row["result"] or "",
        action=row["action"] if "action" in keys else "",
    )


class ApprovalStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._lock = Lock()
        connect(path)

    def _db(self):
        return connect(self.path)

    def create(self, *, principal: Principal, question: str, skill_id: str = "", action: str = "") -> Approval:
        approval = Approval(
            id=str(uuid4()),
            user_id=principal.user_id,
            actor_email=principal.email,
            department=principal.department,
            question=question,
            skill_id=skill_id,
            action=action,
            status="pending",
            created_at=_iso(_now()),
        )
        with self._lock:
            self._db().execute(
                """INSERT INTO approvals
                   (id, user_id, actor_email, department, question, skill_id, action, status, created_at, decided_at, decided_by, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    approval.id,
                    approval.user_id,
                    approval.actor_email,
                    approval.department,
                    approval.question,
                    approval.skill_id,
                    approval.action,
                    approval.status,
                    approval.created_at,
                    "",
                    "",
                    "",
                ),
            )
            self._db().commit()
        return approval

    def get(self, approval_id: str) -> Approval | None:
        if not approval_id:
            return None
        row = self._db().execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        return _from_row(row) if row else None

    def list(self, *, principal: Principal | None = None, status: str | None = None) -> list[Approval]:
        rows = self._db().execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall()
        items = [_from_row(row) for row in rows]
        if status:
            items = [item for item in items if item.status == status]
        if principal and not principal.is_admin and not principal.can_approve():
            items = [item for item in items if item.user_id == principal.user_id]
        return items

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
            self._db().execute(
                "UPDATE approvals SET status = ?, decided_at = ?, decided_by = ?, result = ? WHERE id = ?",
                (approval.status, approval.decided_at, approval.decided_by, approval.result, approval.id),
            )
            self._db().commit()
        return approval

    def mark_executed(self, approval_id: str, result: str) -> Approval | None:
        approval = self.get(approval_id)
        if approval is None:
            return None
        approval.status = "executed"
        approval.result = result
        approval.decided_at = approval.decided_at or _iso(_now())
        with self._lock:
            self._db().execute(
                "UPDATE approvals SET status = ?, decided_at = ?, result = ? WHERE id = ?",
                (approval.status, approval.decided_at, approval.result, approval.id),
            )
            self._db().commit()
        return approval

    def reset(self) -> None:
        with self._lock:
            self._db().execute("DELETE FROM approvals")
            self._db().commit()


approval_store = ApprovalStore()
