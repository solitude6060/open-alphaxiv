from __future__ import annotations

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
    answer_mode: str = "mock"


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
    def root() -> dict[str, Any]:
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
    def codex_status() -> dict[str, Any]:
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
            "auth_modes": ["chatgpt_login", "api_key", "access_token"],
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
    def create_paper(payload: PaperCreate) -> dict[str, Any]:
        try:
            return service().ingest_paper(payload.source)
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

    @app.post("/api/papers/{paper_id}/bookmark")
    def bookmark(paper_id: int, payload: BookmarkUpdate) -> dict[str, Any]:
        return service().update_bookmark(paper_id, payload.bookmarked)

    @app.post("/api/papers/{paper_id}/tags")
    def tags(paper_id: int, payload: TagsUpdate) -> dict[str, Any]:
        return service().update_tags(paper_id, payload.tags)

    @app.post("/api/chat/sessions")
    def chat_session(payload: ChatCreate) -> dict[str, Any]:
        return service().create_chat_session(payload.paper_id, payload.title)

    @app.post("/api/chat/messages")
    def ask(payload: ChatAsk) -> dict[str, Any]:
        try:
            return service().ask(
                payload.paper_id,
                payload.query,
                payload.session_id,
                payload.selected_text,
                payload.answer_mode,
                codex_options(),
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/chat/messages/{message_id}/retrieval")
    def retrieval(message_id: int) -> dict[str, Any]:
        row = service().store.query_one("SELECT metadata_json FROM chat_messages WHERE id = ?", (message_id,))
        if not row:
            raise HTTPException(status_code=404, detail="message not found")
        import json

        return json.loads(row["metadata_json"])

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
        "cwd": Path.cwd(),
    }


app = create_app()
