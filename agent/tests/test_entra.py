from types import SimpleNamespace

from closed_agent.auth import resolve_principal_from_token
from closed_agent.entra import decode_token, principal_from_claims, reset_cache, valid_issuers
from closed_agent.identity import directory
from closed_agent.settings import settings


def test_claims_map_known_oid() -> None:
    principal = principal_from_claims({"oid": "11111111-1111-1111-1111-111111111111"})
    assert principal is not None
    assert principal.email == "admin@example.com"
    assert principal.is_admin


def test_claims_overlay_roles_and_department(monkeypatch) -> None:
    monkeypatch.setattr(settings, "entra_group_departments", "g-sales:営業部")
    principal = principal_from_claims(
        {
            "oid": "22222222-2222-2222-2222-222222222222",
            "roles": ["Approver"],
            "groups": ["g-sales"],
        }
    )
    assert principal is not None
    assert principal.can_approve()
    assert principal.department == "営業部"


def test_unknown_oid_is_rejected() -> None:
    assert principal_from_claims({"oid": "00000000-0000-0000-0000-000000000000", "preferred_username": "x@y"}) is None


def test_unknown_oid_can_be_guest(monkeypatch) -> None:
    monkeypatch.setattr(settings, "entra_allow_unknown", True)
    principal = principal_from_claims(
        {"oid": "00000000-0000-0000-0000-000000000000", "preferred_username": "guest@contoso.com", "department": "営業部"}
    )
    assert principal is not None
    assert principal.department == "営業部"
    assert not principal.is_admin


def test_entra_mode_rejects_local_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "entra")
    monkeypatch.setattr("closed_agent.auth.resolve_bearer", lambda token: None)
    assert resolve_principal_from_token("local-admin") is None


def test_hybrid_keeps_local_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "hybrid")
    found = resolve_principal_from_token("local-sales")
    assert found is not None
    assert found.department == "営業部"


def test_issuers_include_v1_and_v2(monkeypatch) -> None:
    monkeypatch.setattr(settings, "azure_tenant_id", "tenant-id")
    issuers = valid_issuers()
    assert "https://login.microsoftonline.com/tenant-id/v2.0" in issuers
    assert "https://sts.windows.net/tenant-id/" in issuers


def test_decode_requires_tenant(monkeypatch) -> None:
    reset_cache()
    monkeypatch.setattr(settings, "azure_tenant_id", "")
    monkeypatch.setattr(settings, "azure_client_id", "app")
    monkeypatch.setattr(settings, "entra_jwks_url", "")
    assert decode_token("aaa.bbb.ccc") is None


def test_decode_uses_jwks(monkeypatch) -> None:
    reset_cache()
    monkeypatch.setattr(settings, "azure_tenant_id", "tenant")
    monkeypatch.setattr(settings, "azure_client_id", "app")
    monkeypatch.setattr(settings, "entra_jwks_url", "https://example.invalid/keys")

    def fake_client(_url: str) -> SimpleNamespace:
        return SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key="secret-for-test"))

    monkeypatch.setattr("closed_agent.entra._client", fake_client)
    monkeypatch.setattr(
        "closed_agent.entra.jwt.decode",
        lambda *args, **kwargs: {"oid": "11111111-1111-1111-1111-111111111111", "aud": "app"},
    )
    claims = decode_token("header.payload.sig")
    assert claims is not None
    assert directory.resolve_identity(str(claims["oid"])) is not None
