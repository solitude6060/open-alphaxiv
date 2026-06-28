from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .services import PaperService
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
        return service().ask(payload.paper_id, payload.query, payload.session_id)

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


app = create_app()
