from fastapi.testclient import TestClient

from closed_agent.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_is_api() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "closed-agent"
    assert response.json()["app"] == "/app"


def test_skills_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/v1/skills", headers={"Authorization": "Bearer local-admin"})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert "trip-precheck" in ids


def test_cors_allows_admin() -> None:
    client = TestClient(app)
    response = client.options(
        "/v1/skills",
        headers={
            "Origin": "http://admin.localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://admin.localhost"
