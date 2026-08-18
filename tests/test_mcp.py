from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.main import create_app, service
from app.mcp.tools import TOOL_NAMES, call_tool
from app.services import PaperService
from app.store import Store


@pytest.fixture()
def paper_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PaperService:
    monkeypatch.setattr(
        "app.services.arxiv_metadata",
        lambda arxiv_id: {
            "title": f"MCP paper {arxiv_id}",
            "abstract": "Local MCP fixture abstract about attention.",
            "authors": ["MCP Author"],
            "published_at": "2026-08-17T00:00:00Z",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
        },
    )
    monkeypatch.setattr("app.services.fetch_binary", lambda url: b"%PDF-1.4 mcp")
    monkeypatch.setattr("app.services.extract_pdf_text", lambda path: "MCP full paper text.")
    monkeypatch.setattr(
        "app.services.render_pdf_page_images",
        lambda pdf_path, output_dir, max_pages=80: [],
    )
    monkeypatch.setattr("app.services.extract_pdf_text_layers", lambda path, max_pages=80, timeout=30.0: [])
    return PaperService(Store(tmp_path / "mcp.db"), tmp_path / "data")


@pytest.fixture()
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    async def immediate_to_thread(func: Callable[..., object], /, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)

    service.cache_clear()
    monkeypatch.setenv("OPEN_ALPHAXIV_DATABASE_PATH", str(tmp_path / "mcp-api.db"))
    monkeypatch.setenv("OPEN_ALPHAXIV_STORAGE_DIR", str(tmp_path / "mcp-data"))
    monkeypatch.setattr("app.main.to_thread", immediate_to_thread)
    monkeypatch.setattr(
        "app.services.arxiv_metadata",
        lambda arxiv_id: {
            "title": f"MCP HTTP paper {arxiv_id}",
            "abstract": "HTTP MCP fixture.",
            "authors": ["MCP HTTP Author"],
            "published_at": "2026-08-17T00:00:00Z",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
        },
    )
    monkeypatch.setattr("app.services.fetch_binary", lambda url: b"%PDF-1.4 mcp")
    monkeypatch.setattr("app.services.extract_pdf_text", lambda path: "MCP HTTP paper text.")
    monkeypatch.setattr(
        "app.services.render_pdf_page_images",
        lambda pdf_path, output_dir, max_pages=80: [],
    )
    monkeypatch.setattr("app.services.extract_pdf_text_layers", lambda path, max_pages=80, timeout=30.0: [])
    yield create_app()
    service.cache_clear()


def test_mcp_tool_schemas_cover_library_and_arxiv() -> None:
    assert TOOL_NAMES == {
        "search_arxiv",
        "ingest_paper",
        "list_library",
        "get_paper_text",
        "query_paper_pages",
        "save_note",
        "list_notes",
    }


def test_list_library_returns_ingested_paper(paper_service: PaperService) -> None:
    paper = paper_service.ingest_paper("2201.08239")
    result = call_tool("list_library", {}, paper_service)
    ids = [item["id"] for item in result]
    assert paper["id"] in ids
    assert any(item.get("landing_url", "").startswith("https://arxiv.org/abs/") for item in result)


def test_get_paper_text_returns_stored_text(paper_service: PaperService) -> None:
    paper = paper_service.ingest_paper("2201.08239")
    result = call_tool("get_paper_text", {"paper_id": paper["id"]}, paper_service)
    assert result["paper_id"] == paper["id"]
    assert result["landing_url"].startswith("https://arxiv.org/abs/")
    assert "MCP full paper text" in result["text"]
    assert result["character_count"] == len(result["text"])


def test_search_arxiv_only_calls_export_arxiv_org(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_fetch(url: str, timeout: float = 8.0) -> str:
        captured["url"] = url
        return (
            "<feed><entry>"
            "<id>http://arxiv.org/abs/2201.08239</id>"
            "<title>Attention paper</title>"
            "<summary>Transformer abstract.</summary>"
            "<published>2022-01-01T00:00:00Z</published>"
            "<author><name>Test Author</name></author>"
            "</entry></feed>"
        )

    monkeypatch.setattr("app.connectors.arxiv.fetch_text", fake_fetch)
    from app.mcp.tools import search_arxiv

    rows = search_arxiv("attention", max_results=5)
    assert "export.arxiv.org" in captured["url"]
    assert "alphaxiv.org" not in captured["url"]
    assert rows[0]["arxiv_id"] == "2201.08239"
    assert rows[0]["landing_url"] == "https://arxiv.org/abs/2201.08239"


def test_mcp_search_arxiv_is_the_rate_limited_connector() -> None:
    from app.connectors.arxiv import search_arxiv as connector_search
    from app.mcp.tools import search_arxiv as mcp_search

    assert mcp_search is connector_search


@pytest.mark.asyncio
async def test_mcp_http_offloads_handler_off_event_loop(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = {"to_thread": False}

    async def tracking_to_thread(func, /, *args, **kwargs):
        called["to_thread"] = True
        return func(*args, **kwargs)

    monkeypatch.setattr("app.main.to_thread", tracking_to_thread)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert response.status_code == 200
    assert called["to_thread"] is True


@pytest.mark.asyncio
async def test_mcp_http_lists_tools(app: FastAPI) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert response.status_code == 200
    payload = response.json()
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert names == {
        "search_arxiv",
        "ingest_paper",
        "list_library",
        "get_paper_text",
        "query_paper_pages",
        "save_note",
        "list_notes",
    }


def test_query_paper_pages_returns_page_excerpts(paper_service: PaperService) -> None:
    paper = paper_service.ingest_paper("2201.08239")
    result = call_tool(
        "query_paper_pages",
        {"paper_id": paper["id"], "questions": ["MCP paper"]},
        paper_service,
    )
    assert result[0]["question"] == "MCP paper"
    assert result[0]["pages"]
    assert "excerpt" in result[0]["pages"][0]


def test_list_notes_returns_saved_note(paper_service: PaperService) -> None:
    project = paper_service.create_research_project({"title": "MCP notes"})
    saved = call_tool(
        "save_note",
        {
            "project_id": project["id"],
            "title": "Attention note",
            "body_markdown": "The transformer uses attention.",
        },
        paper_service,
    )
    listed = call_tool("list_notes", {"project_id": project["id"], "q": "attention"}, paper_service)
    ids = [note["id"] for note in listed]
    assert saved["id"] in ids
