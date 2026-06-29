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

    monkeypatch.setattr("app.services.fetch_binary", lambda url: b"%PDF-1.4 api fixture")
    monkeypatch.setattr(
        "app.services.extract_pdf_text",
        lambda path: "API full paper text about attention layers and evaluation.",
    )

    def page_images(pdf_path: Path, output_dir: Path, max_pages: int = 12) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        page = output_dir / "page-001.png"
        page.write_bytes(b"png")
        return [page]

    monkeypatch.setattr("app.services.render_pdf_page_images", page_images)
    monkeypatch.setattr(
        "app.services.extract_pdf_text_layers",
        lambda path, max_pages=12, timeout=30.0: [
            {
                "page_number": 1,
                "width": 612.0,
                "height": 792.0,
                "words": [{"text": "Attention", "x": 10.0, "y": 12.0, "width": 8.0, "height": 1.8}],
            }
        ],
    )


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    async def immediate_to_thread(func: Callable[..., object], /, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    service.cache_clear()
    monkeypatch.setenv("OPEN_ALPHAXIV_DATABASE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("OPEN_ALPHAXIV_STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("app.main.to_thread", immediate_to_thread)
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
    assert "host_cli_login" in payload["auth_modes"]
    assert "chatgpt_login" not in payload["auth_modes"]
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
        captured: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            captured["prompt"] = command[-1]
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
                "selected_image": {"page": 1, "x": 10, "y": 20, "width": 30, "height": 40},
                "system_prompt": "Answer in Markdown tables.",
                "answer_mode": "codex",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "HTTP Codex answer [chunk:1]"
    assert payload["retrieval"]["provider"] == "codex"
    assert payload["retrieval"]["answer_mode"] == "codex"
    assert payload["retrieval"]["context_strategy"] == "full_text"
    assert payload["retrieval"]["system_prompt_preview"] == "Answer in Markdown tables."
    assert "Answer in Markdown tables." in str(captured["prompt"])


@pytest.mark.asyncio
async def test_chat_session_history_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        paper_response = await client.post("/api/papers", json={"source": "https://arxiv.org/abs/2201.08239"})
        assert paper_response.status_code == 200
        paper_id = paper_response.json()["id"]

        create_response = await client.post(
            "/api/chat/sessions",
            json={"paper_id": paper_id, "title": "Reading thread"},
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["id"]

        first_response = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"paper_id": paper_id, "query": "What is the topic?"},
        )
        second_response = await client.post(
            "/api/chat/messages",
            json={"paper_id": paper_id, "session_id": session_id, "query": "Continue that answer"},
        )
        list_response = await client.get(f"/api/papers/{paper_id}/chat/sessions")
        get_response = await client.get(f"/api/chat/sessions/{session_id}")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["session_id"] == session_id
    assert second_response.json()["session_id"] == session_id
    assert list_response.status_code == 200
    assert list_response.json()[0]["message_count"] == 4
    assert get_response.status_code == 200
    assert [message["role"] for message in get_response.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


@pytest.mark.asyncio
async def test_paper_full_text_and_page_manifest_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        paper_response = await client.post("/api/papers", json={"source": "https://arxiv.org/abs/2201.08239"})
        assert paper_response.status_code == 200
        paper_id = paper_response.json()["id"]

        text_response = await client.get(f"/api/papers/{paper_id}/fulltext")
        pages_response = await client.get(f"/api/papers/{paper_id}/pages")
        text_layers_response = await client.get(f"/api/papers/{paper_id}/pages/text")
        text_layer_response = await client.get(f"/api/papers/{paper_id}/pages/1/text")
        missing_text_layer_response = await client.get(f"/api/papers/{paper_id}/pages/999/text")
        image_response = await client.get(f"/api/papers/{paper_id}/pages/1.png")

    assert text_response.status_code == 200
    assert "attention layers" in text_response.json()["text"]
    assert pages_response.status_code == 200
    assert pages_response.json()[0]["image_url"].endswith(f"/api/papers/{paper_id}/pages/1.png")
    assert pages_response.json()[0]["text_layer_url"].endswith(f"/api/papers/{paper_id}/pages/1/text")
    assert text_layers_response.status_code == 200
    assert text_layers_response.json()["pages"][0]["words"][0]["text"] == "Attention"
    assert text_layer_response.status_code == 200
    assert text_layer_response.json()["words"][0]["text"] == "Attention"
    assert missing_text_layer_response.status_code == 404
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/png"


@pytest.mark.asyncio
async def test_research_project_note_capture_and_export_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        paper_response = await client.post("/api/papers", json={"source": "https://arxiv.org/abs/2201.08239"})
        assert paper_response.status_code == 200
        paper_id = paper_response.json()["id"]

        project_response = await client.post(
            "/api/research/projects",
            json={
                "title": "Transformer workspace",
                "goal": "Track evidence for implementation.",
                "current_state": "Reading the paper.",
            },
        )
        assert project_response.status_code == 200
        project = project_response.json()

        question_response = await client.post(
            "/api/research/questions",
            json={
                "project_id": project["id"],
                "question": "Which result should be reproduced?",
                "current_answer": "Start with attention layers.",
            },
        )
        project_update_response = await client.patch(
            f"/api/research/projects/{project['id']}",
            json={
                "goal": "Reproduce the attention baseline.",
                "current_state": "Passage evidence saved; implementation is next.",
            },
        )
        passage_response = await client.post(
            f"/api/papers/{paper_id}/research-notes",
            json={
                "project_id": project["id"],
                "title": "Selected evidence",
                "selected_text": "Attention layers are central evidence.",
                "page_number": 4,
            },
        )
        ask_response = await client.post(
            "/api/chat/messages",
            json={"paper_id": paper_id, "query": "What is the paper about?"},
        )
        answer_note_response = await client.post(
            f"/api/chat/messages/{ask_response.json()['message_id']}/research-note",
            json={"project_id": project["id"], "title": "Assistant answer"},
        )
        notes_response = await client.get(f"/api/research/notes?project_id={project['id']}")
        passage_links_response = await client.get(
            f"/api/research/notes/{passage_response.json()['id']}/links"
        )
        export_response = await client.get(f"/api/research/projects/{project['id']}/export.md")

    assert question_response.status_code == 200
    assert project_update_response.status_code == 200
    assert project_update_response.json()["current_state"] == "Passage evidence saved; implementation is next."
    assert passage_response.status_code == 200
    assert answer_note_response.status_code == 200
    assert notes_response.status_code == 200
    assert len(notes_response.json()) == 2
    assert passage_links_response.status_code == 200
    assert passage_links_response.json()[0]["link_type"] == "paper_passage"
    assert passage_links_response.json()[0]["metadata"]["page_number"] == 4
    assert export_response.status_code == 200
    assert "# Transformer workspace" in export_response.text
    assert "Reproduce the attention baseline." in export_response.text
    assert "Passage evidence saved; implementation is next." in export_response.text
    assert "[Deterministic API paper 2201.08239, p.4]" in export_response.text
    assert "Assistant answer" in export_response.text


@pytest.mark.asyncio
async def test_research_link_rejects_unknown_paper_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post("/api/research/projects", json={"title": "Invalid link"})
        note_response = await client.post(
            "/api/research/notes",
            json={
                "project_id": project_response.json()["id"],
                "title": "Evidence note",
                "body_markdown": "Needs a valid paper link.",
            },
        )
        response = await client.post(
            f"/api/research/notes/{note_response.json()['id']}/links",
            json={
                "link_type": "paper_passage",
                "relation": "supports",
                "target_id": "999",
                "quote": "missing paper",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "paper not found"


@pytest.mark.asyncio
async def test_chat_messages_rejects_invalid_answer_mode_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        paper_response = await client.post("/api/papers", json={"source": "https://arxiv.org/abs/2201.08239"})
        assert paper_response.status_code == 200
        paper_id = paper_response.json()["id"]

        response = await client.post(
            "/api/chat/messages",
            json={
                "paper_id": paper_id,
                "query": "Summarize the contribution",
                "answer_mode": "browser_oauth",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "answer_mode must be 'mock' or 'codex'"
