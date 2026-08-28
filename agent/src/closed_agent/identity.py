from __future__ import annotations

from dataclasses import dataclass

from closed_agent.settings import settings

CLEARANCE_RANK = {"internal": 0, "confidential": 1, "restricted": 2}


@dataclass(frozen=True)
class Principal:
    user_id: int
    email: str
    name: str
    department: str
    clearance: str
    roles: frozenset[str]
    token: str = ""
    entra_oid: str = ""
    aliases: frozenset[str] = frozenset()

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    def can_approve(self) -> bool:
        return self.is_admin or "approver" in self.roles

    def can_audit(self) -> bool:
        return self.is_admin or "auditor" in self.roles

    def clearance_rank(self) -> int:
        return CLEARANCE_RANK.get(self.clearance, 0)


def _builtin_users() -> list[Principal]:
    return [
        Principal(
            user_id=1,
            email="admin@example.com",
            name="管理者",
            department="情報システム部",
            clearance="restricted",
            roles=frozenset({"admin", "approver", "auditor"}),
            token="local-admin",
            entra_oid="11111111-1111-1111-1111-111111111111",
            aliases=frozenset({"1", "admin", "aad-admin", "11111111-1111-1111-1111-111111111111"}),
        ),
        Principal(
            user_id=2,
            email="sales@example.com",
            name="営業 太郎",
            department="営業部",
            clearance="confidential",
            roles=frozenset({"user"}),
            token="local-sales",
            entra_oid="22222222-2222-2222-2222-222222222222",
            aliases=frozenset({"sales", "22222222-2222-2222-2222-222222222222"}),
        ),
        Principal(
            user_id=3,
            email="credit@example.com",
            name="与信 花子",
            department="与信室",
            clearance="confidential",
            roles=frozenset({"user"}),
            token="local-credit",
            aliases=frozenset({"credit"}),
        ),
        Principal(
            user_id=4,
            email="contracts@example.com",
            name="契約 次郎",
            department="契約管理部",
            clearance="confidential",
            roles=frozenset({"user"}),
            token="local-contracts",
            aliases=frozenset({"contracts"}),
        ),
        Principal(
            user_id=5,
            email="hr@example.com",
            name="人事 三郎",
            department="人事部",
            clearance="internal",
            roles=frozenset({"user"}),
            token="local-hr",
            aliases=frozenset({"hr"}),
        ),
        Principal(
            user_id=6,
            email="legal@example.com",
            name="法務 四郎",
            department="法務部",
            clearance="confidential",
            roles=frozenset({"approver"}),
            token="local-legal",
            aliases=frozenset({"legal"}),
        ),
        Principal(
            user_id=7,
            email="trade@example.com",
            name="貿易 五郎",
            department="貿易管理部",
            clearance="confidential",
            roles=frozenset({"user"}),
            token="local-trade",
            aliases=frozenset({"trade"}),
        ),
        Principal(
            user_id=8,
            email="compliance@example.com",
            name="コンプラ 六子",
            department="コンプライアンス室",
            clearance="restricted",
            roles=frozenset({"approver", "auditor"}),
            token="local-compliance",
            aliases=frozenset({"compliance"}),
        ),
    ]


class Directory:
    """社内の身元台帳。未知の差出人は管理者に寄せない。"""

    def __init__(self, users: list[Principal] | None = None) -> None:
        self.users = users or _builtin_users()
        self._apply_token_overrides()

    def _apply_token_overrides(self) -> None:
        raw = settings.agent_tokens.strip()
        if not raw:
            return
        overrides: dict[str, str] = {}
        for part in raw.split(","):
            if ":" not in part:
                continue
            key, token = part.split(":", 1)
            overrides[key.strip().lower()] = token.strip()
        if not overrides:
            return
        updated: list[Principal] = []
        for user in self.users:
            keys = {user.email.lower(), *user.aliases, str(user.user_id)}
            token = next((overrides[key] for key in keys if key in overrides), user.token)
            updated.append(
                Principal(
                    user_id=user.user_id,
                    email=user.email,
                    name=user.name,
                    department=user.department,
                    clearance=user.clearance,
                    roles=user.roles,
                    token=token,
                    entra_oid=user.entra_oid,
                    aliases=user.aliases,
                )
            )
        self.users = updated

    def by_token(self, token: str | None) -> Principal | None:
        if not token:
            return None
        needle = token.strip()
        return next((user for user in self.users if user.token and user.token == needle), None)

    def by_user_id(self, user_id: int | None) -> Principal | None:
        if not user_id:
            return None
        return next((user for user in self.users if user.user_id == user_id), None)

    def resolve_identity(self, identity: str | None) -> Principal | None:
        if not identity:
            return None
        key = identity.strip().lower()
        if not key:
            return None
        for user in self.users:
            aliases = {user.email.lower(), user.entra_oid.lower(), *(item.lower() for item in user.aliases)}
            if key in aliases:
                return user
            if key.isdigit() and int(key) == user.user_id:
                return user
        return None


directory = Directory()


def resolve_principal(*, user_id: int | None = None, identity: str | None = None) -> Principal | None:
    found = directory.resolve_identity(identity)
    if found:
        return found
    return directory.by_user_id(user_id)
