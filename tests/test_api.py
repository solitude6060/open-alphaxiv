from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app, service


def minimal_pdf_bytes() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode("ascii"))
        content.extend(obj + b"\n")
        content.extend(b"endobj\n")
    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            f"trailer\n<< /Root 1 0 R /Size {len(objects) + 1} >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(content)


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
async def test_upload_paper_accepts_raw_pdf_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.post(
            "/api/papers/upload",
            content=minimal_pdf_bytes(),
            headers={
                "content-type": "application/pdf",
                "x-filename": "local-api-study.pdf",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["source_type"] == "upload"
    assert payload["title"] == "local api study"
    assert payload["full_text_available"] is True
    assert payload["page_image_count"] == 1


@pytest.mark.asyncio
async def test_upload_paper_rejects_non_pdf_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.post(
            "/api/papers/upload",
            content=b"not a pdf",
            headers={
                "content-type": "text/plain",
                "x-filename": "notes.txt",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "uploaded file must be a PDF"


@pytest.mark.asyncio
async def test_upload_paper_rejects_unparseable_pdf_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.post(
            "/api/papers/upload",
            content=b"%PDF-1.4 header only",
            headers={
                "content-type": "application/pdf",
                "x-filename": "fake.pdf",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "uploaded file must be a parseable PDF"


@pytest.mark.asyncio
async def test_upload_paper_rejects_oversized_pdf_over_http(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.MAX_UPLOAD_PDF_BYTES", 10)

    async with asgi_client(app) as client:
        response = await client.post(
            "/api/papers/upload",
            content=minimal_pdf_bytes(),
            headers={
                "content-type": "application/pdf",
                "x-filename": "large.pdf",
            },
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "uploaded PDF exceeds 10 byte limit"


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
async def test_experiment_runs_can_be_recorded_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post("/api/research/projects", json={"title": "HTTP experiments"})
        project = project_response.json()
        run_response = await client.post(
            "/api/experiments/runs",
            json={
                "project_id": project["id"],
                "title": "HTTP attention run",
                "hypothesis": "Attention should improve BLEU.",
                "dataset": "WMT14 en-de",
                "code_ref": "git:def456",
                "command": "python train.py --seed 3",
                "parameters": {"seed": 3},
                "metrics": {"bleu": 28.8},
                "summary": "First HTTP-recorded run.",
            },
        )
        assert run_response.status_code == 200
        run = run_response.json()
        update_response = await client.patch(
            f"/api/experiments/runs/{run['id']}",
            json={"status": "completed", "metrics": {"bleu": 29.0}, "summary": "Run completed."},
        )
        artifact_response = await client.post(
            f"/api/experiments/runs/{run['id']}/artifacts",
            json={
                "artifact_type": "metrics",
                "uri": "file:///runs/http-attention/metrics.json",
                "label": "HTTP metrics",
                "metadata": {"rows": 10},
            },
        )
        runs_response = await client.get(f"/api/experiments/runs?project_id={project['id']}")
        artifacts_response = await client.get(f"/api/experiments/runs/{run['id']}/artifacts")
        note_response = await client.post(
            f"/api/experiments/runs/{run['id']}/research-note",
            json={"project_id": project["id"], "title": "HTTP experiment note"},
        )
        links_response = await client.get(f"/api/research/notes/{note_response.json()['id']}/links")
        export_response = await client.get(f"/api/research/projects/{project['id']}/export.md")

    assert run_response.status_code == 200
    assert run["status"] == "planned"
    assert update_response.status_code == 200
    assert update_response.json()["metrics"]["bleu"] == 29.0
    assert artifact_response.status_code == 200
    assert artifact_response.json()["label"] == "HTTP metrics"
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1
    assert artifacts_response.status_code == 200
    assert artifacts_response.json()[0]["metadata"]["rows"] == 10
    assert note_response.status_code == 200
    assert links_response.json()[0]["link_type"] == "experiment_run"
    assert "HTTP attention run" in export_response.text
    assert "HTTP metrics" in export_response.text


@pytest.mark.asyncio
async def test_experiment_artifact_rejects_unknown_run_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.post(
            "/api/experiments/runs/999/artifacts",
            json={"artifact_type": "metrics", "uri": "file:///missing.json", "label": "Missing"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment run not found"


@pytest.mark.asyncio
async def test_research_discussions_and_grounding_snapshots_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post(
            "/api/research/projects",
            json={
                "title": "HTTP grounded discussion",
                "goal": "Discuss experiment evidence.",
                "current_state": "Run is ready.",
            },
        )
        project = project_response.json()
        run_response = await client.post(
            "/api/experiments/runs",
            json={
                "project_id": project["id"],
                "title": "HTTP baseline run",
                "dataset": "WMT14 en-de",
                "metrics": {"bleu": 29.2},
                "summary": "HTTP run supports the claim.",
            },
        )
        discussion_response = await client.post(
            "/api/research/discussions",
            json={"project_id": project["id"], "title": "Discuss HTTP run"},
        )
        assert discussion_response.status_code == 200
        discussion = discussion_response.json()
        user_message_response = await client.post(
            f"/api/research/discussions/{discussion['id']}/messages",
            json={"role": "user", "content": "What does this run mean?"},
        )
        assistant_message_response = await client.post(
            f"/api/research/discussions/{discussion['id']}/messages",
            json={"role": "assistant", "content": "The run is consistent with the claim."},
        )
        snapshot_response = await client.post(
            f"/api/research/projects/{project['id']}/grounding-snapshots",
            json={
                "title": "HTTP grounding",
                "discussion_message_id": assistant_message_response.json()["id"],
            },
        )
        discussions_response = await client.get(f"/api/research/discussions?project_id={project['id']}")
        snapshots_response = await client.get(f"/api/research/projects/{project['id']}/grounding-snapshots")
        export_response = await client.get(f"/api/research/projects/{project['id']}/export.md")

    assert run_response.status_code == 200
    assert discussion_response.status_code == 200
    assert user_message_response.status_code == 200
    assert assistant_message_response.status_code == 200
    assert snapshot_response.status_code == 200
    assert "HTTP baseline run" in snapshot_response.json()["content_markdown"]
    assert discussions_response.status_code == 200
    assert discussions_response.json()[0]["message_count"] == 2
    assert snapshots_response.status_code == 200
    assert snapshots_response.json()[0]["title"] == "HTTP grounding"
    assert "## Discussions" in export_response.text
    assert "## Grounding Snapshots" in export_response.text


@pytest.mark.asyncio
async def test_research_discussion_codex_turn_over_http(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post(
            "/api/research/projects",
            json={
                "title": "HTTP Codex discussion project",
                "goal": "Decide the next groundedness experiment.",
                "current_state": "Baseline HTTP run is complete.",
            },
        )
        project = project_response.json()
        await client.post(
            "/api/research/notes",
            json={
                "project_id": project["id"],
                "title": "HTTP Codex evidence",
                "body_markdown": "Tokenizer normalization is a likely groundedness failure source.",
            },
        )
        await client.post(
            "/api/experiments/runs",
            json={
                "project_id": project["id"],
                "title": "HTTP Codex baseline",
                "metrics": {"groundedness": 0.72},
                "summary": "Groundedness misses the target.",
            },
        )
        discussion_response = await client.post(
            "/api/research/discussions",
            json={"project_id": project["id"], "title": "HTTP Codex next steps"},
        )
        discussion = discussion_response.json()
        await client.post(
            f"/api/research/discussions/{discussion['id']}/messages",
            json={"role": "user", "content": "We already ran the HTTP baseline."},
        )

        captured: dict[str, object] = {}

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            captured["prompt"] = command[-1]
            return SimpleNamespace(returncode=0, stdout="Inspect tokenizer failures first.", stderr="")

        monkeypatch.setenv("OPEN_ALPHAXIV_CODEX_ENABLED", "true")
        monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
        monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
        monkeypatch.setattr("app.services.subprocess.run", fake_run)

        response = await client.post(
            f"/api/research/discussions/{discussion['id']}/codex",
            json={
                "content": "What should I try next?",
                "system_prompt": "Answer in Markdown bullets.",
            },
        )
        messages_response = await client.get(f"/api/research/discussions/{discussion['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Inspect tokenizer failures first."
    assert payload["user_message"]["content"] == "What should I try next?"
    assert payload["assistant_message"]["role"] == "assistant"
    assert payload["assistant_message"]["metadata"]["provider"] == "codex"
    assert payload["assistant_message"]["metadata"]["answer_mode"] == "codex"
    assert payload["assistant_message"]["metadata"]["grounding_snapshot_id"] == payload["grounding_snapshot"]["id"]
    assert payload["grounding_snapshot"]["discussion_message_id"] == payload["user_message"]["id"]
    assert [message["role"] for message in messages_response.json()["messages"]] == ["user", "user", "assistant"]
    prompt = str(captured["prompt"])
    assert "HTTP Codex evidence" in prompt
    assert "HTTP Codex baseline" in prompt
    assert "Baseline HTTP run is complete." in prompt
    assert "We already ran the HTTP baseline." in prompt
    assert "Answer in Markdown bullets." in prompt


@pytest.mark.asyncio
async def test_research_discussion_codex_requires_enablement_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post("/api/research/projects", json={"title": "HTTP disabled Codex"})
        discussion_response = await client.post(
            "/api/research/discussions",
            json={"project_id": project_response.json()["id"], "title": "Disabled Codex"},
        )
        response = await client.post(
            f"/api/research/discussions/{discussion_response.json()['id']}/codex",
            json={"content": "Try Codex"},
        )

    assert response.status_code == 400
    assert "OPEN_ALPHAXIV_CODEX_ENABLED" in response.json()["detail"]


@pytest.mark.asyncio
async def test_grounding_snapshot_rejects_unknown_project_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        response = await client.post(
            "/api/research/projects/999/grounding-snapshots",
            json={"title": "Missing"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "research project not found"


@pytest.mark.asyncio
async def test_research_dashboard_and_search_over_http(app: FastAPI) -> None:
    async with asgi_client(app) as client:
        project_response = await client.post(
            "/api/research/projects",
            json={
                "title": "HTTP dashboard project",
                "goal": "Track retrieval quality.",
                "current_state": "Collecting evidence.",
            },
        )
        project = project_response.json()
        await client.post(
            "/api/research/questions",
            json={"project_id": project["id"], "question": "Does retrieval quality improve?"},
        )
        await client.post(
            "/api/research/notes",
            json={
                "project_id": project["id"],
                "title": "Retrieval note",
                "body_markdown": "Retrieval quality improved after context cleanup.",
            },
        )
        await client.post(
            "/api/experiments/runs",
            json={
                "project_id": project["id"],
                "title": "Retrieval experiment",
                "summary": "Context cleanup improved retrieval quality.",
            },
        )
        discussion_response = await client.post(
            "/api/research/discussions",
            json={"project_id": project["id"], "title": "Retrieval discussion"},
        )
        await client.post(
            f"/api/research/discussions/{discussion_response.json()['id']}/messages",
            json={"content": "Discuss retrieval quality."},
        )
        await client.post(f"/api/research/projects/{project['id']}/grounding-snapshots", json={"title": "Retrieval snapshot"})

        dashboard_response = await client.get("/api/research/dashboard")
        search_response = await client.get("/api/research/search?q=retrieval")
        scoped_response = await client.get(f"/api/research/search?q=retrieval&project_id={project['id']}")
        missing_scope_response = await client.get("/api/research/search?q=retrieval&project_id=999")

    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["counts"]["projects"] == 1
    assert dashboard_response.json()["active_projects"][0]["title"] == "HTTP dashboard project"
    assert search_response.status_code == 200
    assert any(result["type"] == "research_note" for result in search_response.json())
    assert any(result["type"] == "research_discussion_message" for result in search_response.json())
    assert scoped_response.status_code == 200
    assert all(result["project_id"] == project["id"] for result in scoped_response.json())
    assert missing_scope_response.status_code == 404
    assert missing_scope_response.json()["detail"] == "research project not found"


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
