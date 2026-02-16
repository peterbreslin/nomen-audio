from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "0.1.0"}


def test_health_cors_headers() -> None:
    resp = client.get("/health", headers={"Origin": "http://localhost:1420"})
    assert resp.headers["access-control-allow-origin"] == "*"
