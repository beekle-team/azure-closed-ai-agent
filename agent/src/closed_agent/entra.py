from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

from dataclasses import replace

from closed_agent.identity import Principal, directory
from closed_agent.settings import settings

_jwks_clients: dict[str, PyJWKClient] = {}


def jwks_url() -> str:
    if settings.entra_jwks_url.strip():
        return settings.entra_jwks_url.strip()
    tenant = settings.azure_tenant_id.strip()
    if not tenant:
        return ""
    return f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"


def issuer() -> str:
    issuers = valid_issuers()
    return issuers[0] if issuers else ""


def valid_issuers() -> list[str]:
    tenant = settings.azure_tenant_id.strip()
    if not tenant:
        return []
    return [
        f"https://login.microsoftonline.com/{tenant}/v2.0",
        f"https://sts.windows.net/{tenant}/",
    ]


def _client(url: str) -> PyJWKClient:
    cached = _jwks_clients.get(url)
    if cached is None:
        cached = PyJWKClient(url, cache_jwk_set=True, lifespan=3600)
        _jwks_clients[url] = cached
    return cached


def decode_token(token: str) -> dict[str, Any] | None:
    """Entra の JWT を検証する。署名・iss・aud・exp を見る。失敗は None。"""
    url = jwks_url()
    tenant = settings.azure_tenant_id.strip()
    audience = settings.azure_client_id.strip()
    if not url or not tenant or not audience:
        return None
    try:
        signing_key = _client(url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=valid_issuers(),
            options={"require": ["exp", "iss", "aud"]},
        )
    except (jwt.PyJWTError, httpx.HTTPError, ValueError):
        return None


def _parse_map(raw: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for part in raw.split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        if key.strip() and value.strip():
            mapping[key.strip()] = value.strip()
    return mapping


def roles_from_claims(claims: dict[str, Any]) -> frozenset[str]:
    mapping = _parse_map(settings.entra_role_map)
    raw = claims.get("roles") or []
    if isinstance(raw, str):
        raw = [raw]
    found: set[str] = set()
    for item in raw:
        key = str(item)
        if key in mapping:
            found.add(mapping[key])
        elif key.lower() in {"admin", "approver", "auditor", "user"}:
            found.add(key.lower())
    return frozenset(found)


def department_from_claims(claims: dict[str, Any]) -> str:
    department = str(claims.get("department") or "").strip()
    if department:
        return department
    mapping = _parse_map(settings.entra_group_departments)
    groups = claims.get("groups") or []
    if isinstance(groups, str):
        groups = [groups]
    for group in groups:
        if str(group) in mapping:
            return mapping[str(group)]
    return ""


def principal_from_claims(claims: dict[str, Any]) -> Principal | None:
    oid = str(claims.get("oid") or claims.get("sub") or "").strip()
    email = str(claims.get("preferred_username") or claims.get("upn") or claims.get("email") or "").strip()
    found = directory.resolve_identity(oid) or directory.resolve_identity(email)
    extra_roles = roles_from_claims(claims)
    department = department_from_claims(claims)
    if found:
        return replace(
            found,
            department=department or found.department,
            roles=found.roles | extra_roles,
        )
    if not settings.entra_allow_unknown:
        return None
    roles = extra_roles or frozenset({"user"})
    name = str(claims.get("name") or email or oid or "unknown")
    clearance = "internal"
    if "admin" in roles or "auditor" in roles:
        clearance = "restricted"
    elif "approver" in roles:
        clearance = "confidential"
    return Principal(
        user_id=abs(hash(oid or email)) % 10_000_000 + 1000,
        email=email or f"{oid}@unknown",
        name=name,
        department=department or "全社",
        clearance=clearance,
        roles=roles,
        entra_oid=oid,
        aliases=frozenset({oid, email} - {""}),
    )


def resolve_bearer(token: str) -> Principal | None:
    claims = decode_token(token)
    if claims is None:
        return None
    return principal_from_claims(claims)


def ready() -> bool:
    return bool(jwks_url() and settings.azure_tenant_id.strip() and settings.azure_client_id.strip())


def reset_cache() -> None:
    _jwks_clients.clear()
    time.sleep(0)
