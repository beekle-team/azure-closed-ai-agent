from __future__ import annotations

from fastapi import Header, HTTPException, Request

from closed_agent.entra import resolve_bearer
from closed_agent.identity import Principal, directory
from closed_agent.ratelimit import rate_limiter
from closed_agent.settings import settings


def _extract_token(authorization: str | None, x_agent_token: str | None) -> str:
    if x_agent_token and x_agent_token.strip():
        return x_agent_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return ""


def resolve_principal_from_token(token: str) -> Principal | None:
    mode = (settings.auth_mode or "local").strip().lower()
    if mode in {"local", "hybrid"}:
        found = directory.by_token(token)
        if found:
            return found
    if mode in {"entra", "hybrid"}:
        found = resolve_bearer(token)
        if found:
            return found
    return None


def require_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
) -> Principal:
    token = _extract_token(authorization, x_agent_token)
    principal = resolve_principal_from_token(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="身元トークンが無い、または未知です")
    key = f"{principal.user_id}:{request.url.path}"
    if not rate_limiter.allow(key):
        raise HTTPException(status_code=429, detail="短時間の利用上限です")
    request.state.principal = principal
    return principal


def require_approver(principal: Principal) -> Principal:
    if not principal.can_approve():
        raise HTTPException(status_code=403, detail="承認する権限がありません")
    return principal


def require_auditor(principal: Principal) -> Principal:
    if not principal.can_audit():
        raise HTTPException(status_code=403, detail="監査ログを見る権限がありません")
    return principal


def require_webhook(
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> None:
    expected = settings.channel_webhook_secret.strip()
    if not expected or x_webhook_secret != expected:
        raise HTTPException(status_code=401, detail="チャネルの共有秘密が違います")
