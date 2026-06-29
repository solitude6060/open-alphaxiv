from __future__ import annotations

from asyncio import to_thread
from functools import lru_cache
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .services import PaperService, codex_credentials_available, resolve_executable
from .store import Store


class ProviderCreate(BaseModel):
    name: str = "Mock provider"
    provider_kind: str = "generation"
    provider_type: str = "mock"
    base_url: str = ""
    model: str = "mock-research-model"
    wire_api: str = "chat_completions"
    api_key: str = ""
    is_default: bool = True


class PaperCreate(BaseModel):
    source: str = Field(..., examples=["https://arxiv.org/abs/2201.08239"])


class BookmarkUpdate(BaseModel):
    bookmarked: bool


class TagsUpdate(BaseModel):
    tags: list[str]


class ChatCreate(BaseModel):
    paper_id: int
    title: str = "Paper chat"


class ChatAsk(BaseModel):
    paper_id: int
    query: str
    session_id: int | None = None
    selected_text: str = ""
    selected_image: dict[str, Any] | None = None
    system_prompt: str = ""
    answer_mode: str = "mock"


class ResearchProjectCreate(BaseModel):
    title: str
    slug: str = ""
    status: str = "active"
    goal: str = ""
    current_state: str = ""


class ResearchProjectUpdate(BaseModel):
    title: str | None = None
    slug: str | None = None
    status: str | None = None
    goal: str | None = None
    current_state: str | None = None


class ResearchQuestionCreate(BaseModel):
    project_id: int
    question: str
    status: str = "open"
    current_answer: str = ""


class ResearchQuestionUpdate(BaseModel):
    question: str | None = None
    status: str | None = None
    current_answer: str | None = None


class ResearchNoteCreate(BaseModel):
    project_id: int
    title: str
    body_markdown: str = ""
    note_type: str = "idea"
    status: str = "active"
    tags: list[str] = Field(default_factory=list)


class ResearchNoteUpdate(BaseModel):
    title: str | None = None
    body_markdown: str | None = None
    note_type: str | None = None
    status: str | None = None
    tags: list[str] | None = None


class ResearchLinkCreate(BaseModel):
    link_type: str
    relation: str
    target_id: str = ""
    target_uri: str = ""
    label: str = ""
    quote: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaperResearchNoteCreate(BaseModel):
    project_id: int
    title: str = ""
    selected_text: str = ""
    page_number: int | None = None
    selected_image: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)


class ChatMessageResearchNoteCreate(BaseModel):
    project_id: int
    title: str = ""
    tags: list[str] = Field(default_factory=list)


class ExperimentRunCreate(BaseModel):
    project_id: int
    title: str
    status: str = "planned"
    hypothesis: str = ""
    dataset: str = ""
    code_ref: str = ""
    command: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    started_at: str = ""
    completed_at: str = ""


class ExperimentRunUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    hypothesis: str | None = None
    dataset: str | None = None
    code_ref: str | None = None
    command: str | None = None
    parameters: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    summary: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ExperimentArtifactCreate(BaseModel):
    artifact_type: str = "other"
    uri: str = ""
    label: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentRunResearchNoteCreate(BaseModel):
    project_id: int | None = None
    title: str = ""
    tags: list[str] = Field(default_factory=list)


class ResearchDiscussionCreate(BaseModel):
    project_id: int
    title: str
    status: str = "active"


class ResearchDiscussionMessageCreate(BaseModel):
    role: str = "user"
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class GroundingSnapshotCreate(BaseModel):
    title: str = ""
    discussion_message_id: int | None = None


@lru_cache(maxsize=1)
def service() -> PaperService:
    settings = get_settings()
    return PaperService(Store(settings.database_path), settings.storage_dir)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Open AlphaXiv Local", version="0.1.0-mvp1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.cors_origin,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "name": "Open AlphaXiv Local",
            "status": "ok",
            "version": "0.1.0-mvp1",
            "web_url": settings.cors_origin,
            "api_health_url": "/api/health",
            "api_docs_url": "/docs",
        }

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": "0.1.0-mvp1", "storage_dir": str(settings.storage_dir)}

    @app.get("/api/codex/status")
    async def codex_status() -> dict[str, Any]:
        cli_path = resolve_executable(settings.codex_cli_path)
        access_token_present = bool(os.environ.get("CODEX_ACCESS_TOKEN"))
        api_key_present = bool(os.environ.get("CODEX_API_KEY"))
        auth_json_path = os.environ.get("CODEX_AUTH_JSON_PATH", "")
        auth_json_configured = bool(auth_json_path and Path(auth_json_path).exists())
        default_auth_json = (
            Path(settings.codex_home) / "auth.json"
            if settings.codex_home
            else Path.home() / ".codex" / "auth.json"
        )
        default_auth_json_configured = default_auth_json.exists()
        credentials_available = codex_credentials_available(codex_options())
        chat_available = bool(settings.codex_enabled and cli_path and credentials_available)
        return {
            "status": "ready" if chat_available else "not_configured",
            "codex_agent_enabled": settings.codex_enabled,
            "codex_chat_available": chat_available,
            "codex_cli_available": bool(cli_path),
            "codex_cli_path": cli_path or settings.codex_cli_path,
            "codex_access_token_present": access_token_present,
            "codex_api_key_present": api_key_present,
            "codex_auth_json_configured": auth_json_configured,
            "codex_default_auth_json_configured": default_auth_json_configured,
            "auth_modes": ["host_cli_login", "api_key", "access_token"],
            "integration_boundary": (
                "Paper chat can use Codex through local codex exec when the backend enables it. "
                "This is a local agent connector, not a browser OAuth model-provider flow."
            ),
        }

    @app.post("/api/providers")
    def create_provider(payload: ProviderCreate) -> dict[str, Any]:
        return service().create_provider(payload.model_dump())

    @app.get("/api/providers")
    def list_providers() -> list[dict[str, Any]]:
        return service().list_providers()

    @app.post("/api/providers/{provider_id}/healthcheck")
    def healthcheck_provider(provider_id: int) -> dict[str, Any]:
        try:
            return service().healthcheck_provider(provider_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/papers")
    async def create_paper(payload: PaperCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().ingest_paper, payload.source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/papers")
    def list_papers(q: str = "") -> list[dict[str, Any]]:
        return service().list_papers(q)

    @app.get("/api/papers/{paper_id}")
    def get_paper(paper_id: int) -> dict[str, Any]:
        try:
            return service().get_paper(paper_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/papers/{paper_id}/chunks")
    def chunks(paper_id: int) -> list[dict[str, Any]]:
        return service().chunks(paper_id)

    @app.get("/api/papers/{paper_id}/fulltext")
    async def paper_fulltext(paper_id: int) -> dict[str, Any]:
        try:
            return service().paper_text(paper_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/papers/{paper_id}/pages")
    async def paper_pages(paper_id: int) -> list[dict[str, Any]]:
        return service().paper_pages(paper_id)

    @app.get("/api/papers/{paper_id}/pages/text")
    async def paper_text_layers(paper_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().paper_text_layers, paper_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/papers/{paper_id}/pages/{page_number}.png")
    async def paper_page_image(paper_id: int, page_number: int) -> Response:
        try:
            path = service().paper_page_image_path(paper_id, page_number)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(content=path.read_bytes(), media_type="image/png")

    @app.get("/api/papers/{paper_id}/pages/{page_number}/text")
    async def paper_page_text(paper_id: int, page_number: int) -> dict[str, Any]:
        try:
            return await to_thread(service().paper_page_text_layer, paper_id, page_number)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/papers/{paper_id}/bookmark")
    def bookmark(paper_id: int, payload: BookmarkUpdate) -> dict[str, Any]:
        return service().update_bookmark(paper_id, payload.bookmarked)

    @app.post("/api/papers/{paper_id}/tags")
    def tags(paper_id: int, payload: TagsUpdate) -> dict[str, Any]:
        return service().update_tags(paper_id, payload.tags)

    @app.post("/api/chat/sessions")
    async def chat_session(payload: ChatCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_chat_session, payload.paper_id, payload.title)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/papers/{paper_id}/chat/sessions")
    async def paper_chat_sessions(paper_id: int) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().list_chat_sessions, paper_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/chat/sessions/{session_id}")
    async def get_chat_session(session_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_chat_session, session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/chat/messages")
    async def ask(payload: ChatAsk) -> dict[str, Any]:
        try:
            return await to_thread(
                service().ask,
                paper_id=payload.paper_id,
                query=payload.query,
                session_id=payload.session_id,
                selected_text=payload.selected_text,
                selected_image=payload.selected_image,
                system_prompt=payload.system_prompt,
                answer_mode=payload.answer_mode,
                codex_options=codex_options(),
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/chat/sessions/{session_id}/messages")
    async def ask_in_session(session_id: int, payload: ChatAsk) -> dict[str, Any]:
        return await ask(payload.model_copy(update={"session_id": session_id}))

    @app.get("/api/chat/messages/{message_id}/retrieval")
    def retrieval(message_id: int) -> dict[str, Any]:
        row = service().store.query_one("SELECT metadata_json FROM chat_messages WHERE id = ?", (message_id,))
        if not row:
            raise HTTPException(status_code=404, detail="message not found")
        import json

        return json.loads(row["metadata_json"])

    @app.post("/api/research/projects")
    async def create_research_project(payload: ResearchProjectCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_project, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/research/projects")
    async def list_research_projects(status: str = "") -> list[dict[str, Any]]:
        return await to_thread(service().list_research_projects, status)

    @app.get("/api/research/projects/{project_id}")
    async def get_research_project(project_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_research_project, project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/research/projects/{project_id}")
    async def update_research_project(project_id: int, payload: ResearchProjectUpdate) -> dict[str, Any]:
        try:
            return await to_thread(
                service().update_research_project,
                project_id,
                payload.model_dump(exclude_unset=True),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/research/projects/{project_id}/export.md")
    async def export_research_project(project_id: int) -> Response:
        try:
            markdown = await to_thread(service().export_research_project, project_id)
            return Response(content=markdown, media_type="text/markdown")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/research/questions")
    async def create_research_question(payload: ResearchQuestionCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_question, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/research/questions")
    async def list_research_questions(project_id: int | None = None, status: str = "") -> list[dict[str, Any]]:
        return await to_thread(service().list_research_questions, project_id, status)

    @app.patch("/api/research/questions/{question_id}")
    async def update_research_question(question_id: int, payload: ResearchQuestionUpdate) -> dict[str, Any]:
        try:
            return await to_thread(
                service().update_research_question,
                question_id,
                payload.model_dump(exclude_unset=True),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/research/notes")
    async def create_research_note(payload: ResearchNoteCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_note, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/research/notes")
    async def list_research_notes(
        project_id: int | None = None,
        q: str = "",
        status: str = "",
        note_type: str = "",
        tag: str = "",
    ) -> list[dict[str, Any]]:
        return await to_thread(service().list_research_notes, project_id, q, status, note_type, tag)

    @app.get("/api/research/notes/{note_id}")
    async def get_research_note(note_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_research_note, note_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/research/notes/{note_id}")
    async def update_research_note(note_id: int, payload: ResearchNoteUpdate) -> dict[str, Any]:
        try:
            return await to_thread(service().update_research_note, note_id, payload.model_dump(exclude_unset=True))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/research/notes/{note_id}/links")
    async def create_research_link(note_id: int, payload: ResearchLinkCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_link, note_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            detail = str(exc.args[0])
            status_code = 404 if detail == "research note not found" else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc

    @app.get("/api/research/notes/{note_id}/links")
    async def research_note_links(note_id: int) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().research_note_links, note_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/papers/{paper_id}/research-notes")
    async def create_paper_research_note(paper_id: int, payload: PaperResearchNoteCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_paper_research_note, paper_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/chat/messages/{message_id}/research-note")
    async def create_chat_message_research_note(
        message_id: int,
        payload: ChatMessageResearchNoteCreate,
    ) -> dict[str, Any]:
        try:
            return await to_thread(service().create_chat_message_research_note, message_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/experiments/runs")
    async def create_experiment_run(payload: ExperimentRunCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_experiment_run, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.get("/api/experiments/runs")
    async def list_experiment_runs(
        project_id: int | None = None,
        status: str = "",
    ) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().list_experiment_runs, project_id, status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/experiments/runs/{run_id}")
    async def get_experiment_run(run_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_experiment_run, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.patch("/api/experiments/runs/{run_id}")
    async def update_experiment_run(run_id: int, payload: ExperimentRunUpdate) -> dict[str, Any]:
        try:
            return await to_thread(
                service().update_experiment_run,
                run_id,
                payload.model_dump(exclude_unset=True),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/experiments/runs/{run_id}/artifacts")
    async def create_experiment_artifact(run_id: int, payload: ExperimentArtifactCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_experiment_artifact, run_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.get("/api/experiments/runs/{run_id}/artifacts")
    async def experiment_run_artifacts(run_id: int) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().experiment_run_artifacts, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/experiments/runs/{run_id}/research-note")
    async def create_experiment_research_note(
        run_id: int,
        payload: ExperimentRunResearchNoteCreate,
    ) -> dict[str, Any]:
        try:
            return await to_thread(service().create_experiment_research_note, run_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/research/discussions")
    async def create_research_discussion(payload: ResearchDiscussionCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_discussion, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.get("/api/research/discussions")
    async def list_research_discussions(
        project_id: int | None = None,
        status: str = "",
    ) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().list_research_discussions, project_id, status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/research/discussions/{discussion_id}")
    async def get_research_discussion(discussion_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_research_discussion, discussion_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/research/discussions/{discussion_id}/messages")
    async def create_research_discussion_message(
        discussion_id: int,
        payload: ResearchDiscussionMessageCreate,
    ) -> dict[str, Any]:
        try:
            return await to_thread(service().create_research_discussion_message, discussion_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/research/projects/{project_id}/grounding-snapshots")
    async def create_grounding_snapshot(project_id: int, payload: GroundingSnapshotCreate) -> dict[str, Any]:
        try:
            return await to_thread(service().create_grounding_snapshot, project_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.get("/api/research/projects/{project_id}/grounding-snapshots")
    async def list_grounding_snapshots(project_id: int) -> list[dict[str, Any]]:
        try:
            return await to_thread(service().list_grounding_snapshots, project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.get("/api/research/grounding-snapshots/{snapshot_id}")
    async def get_grounding_snapshot(snapshot_id: int) -> dict[str, Any]:
        try:
            return await to_thread(service().get_grounding_snapshot, snapshot_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc

    @app.post("/api/papers/{paper_id}/literature-graph/build")
    def build_graph(paper_id: int) -> dict[str, Any]:
        return service().build_literature_graph(paper_id)

    @app.get("/api/papers/{paper_id}/literature-graph")
    def graph(paper_id: int, view: str = "related") -> dict[str, Any]:
        return service().literature_graph(paper_id, view)

    @app.get("/api/papers/{paper_id}/export.md")
    def export_markdown(paper_id: int) -> Response:
        return Response(service().export_markdown(paper_id), media_type="text/markdown")

    return app


def codex_options() -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.codex_enabled,
        "cli_path": settings.codex_cli_path,
        "model": settings.codex_model,
        "timeout_seconds": settings.codex_timeout_seconds,
        "sandbox": settings.codex_sandbox,
        "codex_home": settings.codex_home,
    }


app = create_app()
