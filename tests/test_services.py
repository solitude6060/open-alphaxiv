from __future__ import annotations

from pathlib import Path

import pytest

from app.services import PaperService, normalize_arxiv_id
from app.store import Store


@pytest.fixture()
def service(tmp_path: Path) -> PaperService:
    return PaperService(Store(tmp_path / "test.db"), tmp_path / "data")


def test_normalize_arxiv_id_from_url() -> None:
    assert normalize_arxiv_id("https://arxiv.org/abs/2201.08239v2") == "2201.08239"


def test_ingest_paper_creates_ready_chunks_and_graph(service: PaperService) -> None:
    paper = service.ingest_paper("https://arxiv.org/abs/2201.08239")

    assert paper["status"] == "ready"
    assert paper["arxiv_id"] == "2201.08239"
    assert paper["chunk_count"] >= 3
    assert len(service.chunks(paper["id"])) >= 3
    graph = service.literature_graph(paper["id"])
    assert len(graph["nodes"]) >= 20
    assert graph["edges"]


def test_provider_healthcheck_and_redaction(service: PaperService) -> None:
    provider = service.create_provider({"name": "local", "api_key": "secret"})
    assert provider["has_api_key"] is True
    assert "api_key" not in provider
    result = service.healthcheck_provider(provider["id"])
    assert result["status"] == "ok"


def test_chat_answer_has_citations_and_retrieval(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    answer = service.ask(paper["id"], "What is the paper about?")

    assert "Sources:" in answer["answer"]
    assert answer["citations"]
    assert answer["retrieval"]["retrieved_chunk_ids"]


def test_bookmark_tags_and_export(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    updated = service.update_bookmark(paper["id"], True)
    tagged = service.update_tags(paper["id"], ["rag", "graphs", "rag"])
    exported = service.export_markdown(paper["id"])

    assert updated["bookmarked"] is True
    assert tagged["tags"] == ["graphs", "rag"]
    assert "# " in exported
    assert "Literature Graph Snapshot" in exported

