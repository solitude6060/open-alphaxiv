from __future__ import annotations

import json
from typing import Any

from ..connectors.arxiv import search_arxiv
from ..services import PaperService, normalize_arxiv_id


TOOL_NAMES = {
    "search_arxiv",
    "ingest_paper",
    "list_library",
    "get_paper_text",
    "query_paper_pages",
    "save_note",
    "list_notes",
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_arxiv",
        "description": "Search arXiv metadata via export.arxiv.org. Returns titles, abstracts, and landing URLs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ingest_paper",
        "description": "Import an arXiv paper into the local library by identifier.",
        "inputSchema": {
            "type": "object",
            "properties": {"arxiv_id": {"type": "string"}},
            "required": ["arxiv_id"],
        },
    },
    {
        "name": "list_library",
        "description": "List papers already stored in the local library.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_paper_text",
        "description": "Return extracted text already stored for a local paper.",
        "inputSchema": {
            "type": "object",
            "properties": {"paper_id": {"type": "integer"}},
            "required": ["paper_id"],
        },
    },
    {
        "name": "query_paper_pages",
        "description": "Return page-bounded excerpts for a list of questions about a local paper.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_id": {"type": "integer"},
                "questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 2},
            },
            "required": ["paper_id", "questions"],
        },
    },
    {
        "name": "save_note",
        "description": "Write a research note on a local research project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "title": {"type": "string"},
                "body_markdown": {"type": "string"},
            },
            "required": ["project_id", "title", "body_markdown"],
        },
    },
    {
        "name": "list_notes",
        "description": "Search research notes in a project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "q": {"type": "string"},
            },
        },
    },
]


def _list_library(paper_service: PaperService) -> list[dict[str, Any]]:
    papers = paper_service.list_papers()
    return [
        {
            "id": paper["id"],
            "title": paper["title"],
            "arxiv_id": paper.get("arxiv_id") or paper.get("source_id"),
            "landing_url": paper.get("landing_url") or "",
            "status": paper.get("status"),
            "bookmarked": paper.get("bookmarked"),
            "tags": paper.get("tags") or [],
        }
        for paper in papers
    ]


def call_tool(name: str, arguments: dict[str, Any], paper_service: PaperService) -> Any:
    if name not in TOOL_NAMES:
        raise ValueError(f"unknown MCP tool: {name}")
    args = arguments or {}
    if name == "search_arxiv":
        return search_arxiv(str(args.get("query") or ""), int(args.get("max_results") or 10))
    if name == "ingest_paper":
        arxiv_id = normalize_arxiv_id(str(args.get("arxiv_id") or ""))
        paper = paper_service.ingest_paper(arxiv_id)
        return {
            "id": paper["id"],
            "title": paper["title"],
            "arxiv_id": paper.get("arxiv_id") or paper.get("source_id"),
            "landing_url": paper.get("landing_url") or "",
            "status": paper.get("status"),
        }
    if name == "list_library":
        return _list_library(paper_service)
    if name == "get_paper_text":
        paper_id = int(args.get("paper_id") or 0)
        paper = paper_service.get_paper(paper_id)
        payload = paper_service.paper_text(paper_id)
        return {
            "paper_id": paper_id,
            "title": paper["title"],
            "landing_url": paper.get("landing_url") or "",
            "source": payload["source"],
            "text": payload["text"],
            "character_count": payload["character_count"],
        }
    if name == "query_paper_pages":
        return paper_service.query_paper_pages(
            int(args.get("paper_id") or 0),
            args.get("questions") or [],
            int(args.get("limit") or 2),
        )
    if name == "list_notes":
        project_id_raw = args.get("project_id")
        project_id = int(project_id_raw) if project_id_raw not in {None, ""} else None
        notes = paper_service.list_research_notes(project_id=project_id, q=str(args.get("q") or ""))
        return [
            {
                "id": note["id"],
                "project_id": note["project_id"],
                "title": note["title"],
                "note_type": note.get("note_type"),
                "body_markdown": note.get("body_markdown"),
            }
            for note in notes
        ]
    note = paper_service.create_research_note(
        {
            "project_id": int(args.get("project_id") or 0),
            "title": str(args.get("title") or ""),
            "body_markdown": str(args.get("body_markdown") or ""),
        }
    )
    return {
        "id": note["id"],
        "project_id": note["project_id"],
        "title": note["title"],
        "body_markdown": note["body_markdown"],
    }


def tool_result_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)
