from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app, service


@pytest.fixture(autouse=True)
def deterministic_arxiv_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def metadata(arxiv_id: str) -> dict[str, object]:
        return {
            "title": f"Deterministic API paper {arxiv_id}",
            "abstract": (
                "This local API fixture describes retrieval augmented reading, "
                "selected passages, and cited paper question answering."
            ),
            "authors": ["API Test Author"],
            "published_at": "2026-06-28T00:00:00Z",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
        }

    monkeypatch.setattr("app.services.arxiv_metadata", metadata)


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    async def immediate_to_thread(func: Callable[..., object], /, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    service.cache_clear()
    monkeypatch.setenv("OPEN_ALPHAXIV_DATABASE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("OPEN_ALPHAXIV_STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("app.main.asyncio.to_thread", immediate_to_thread)
    yield create_app()
    service.cache_clear()


def asgi_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_root_endpoint_points_to_api_entrypoints(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_health_url"] == "/api/health"
    assert payload["api_docs_url"] == "/docs"


@pytest.mark.asyncio
async def test_codex_status_describes_local_connector_boundary(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.get("/api/codex/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "not_configured"}
    assert "chatgpt_login" in payload["auth_modes"]
    assert "local agent connector" in payload["integration_boundary"]
    assert "codex_agent_enabled" in payload
    assert "codex_chat_available" in payload
    assert "codex_access_token_present" in payload


@pytest.mark.asyncio
async def test_chat_messages_accepts_codex_answer_mode_over_http(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with asgi_client(app) as client:
        paper_response = await client.post("/api/papers", json={"source": "https://arxiv.org/abs/2201.08239"})
        assert paper_response.status_code == 200
        paper_id = paper_response.json()["id"]

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(returncode=0, stdout="HTTP Codex answer [chunk:1]", stderr="")

        monkeypatch.setenv("OPEN_ALPHAXIV_CODEX_ENABLED", "true")
        monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
        monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
        monkeypatch.setattr("app.services.subprocess.run", fake_run)

        response = await client.post(
            "/api/chat/messages",
            json={
                "paper_id": paper_id,
                "query": "Summarize the contribution",
                "selected_text": "selected API context",
                "answer_mode": "codex",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "HTTP Codex answer [chunk:1]"
    assert payload["retrieval"]["provider"] == "codex"
    assert payload["retrieval"]["answer_mode"] == "codex"
