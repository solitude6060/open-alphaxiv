from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_root_endpoint_points_to_api_entrypoints() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["api_health_url"] == "/api/health"
    assert response.json()["api_docs_url"] == "/docs"

