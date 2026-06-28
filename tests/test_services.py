from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from app.services import PaperService, build_codex_paper_prompt, normalize_arxiv_id
from app.store import Store


@pytest.fixture(autouse=True)
def deterministic_arxiv_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def metadata(arxiv_id: str) -> dict[str, object]:
        return {
            "title": f"Deterministic test paper {arxiv_id}",
            "abstract": (
                "This local fixture describes retrieval augmented reading, graph extraction, "
                "chunk citations, and selected passage question answering for repeatable tests."
            ),
            "authors": ["Test Author"],
            "published_at": "2026-06-28T00:00:00Z",
            "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
        }

    monkeypatch.setattr("app.services.arxiv_metadata", metadata)


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


def test_chat_uses_selected_text_as_question_focus(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    answer = service.ask(
        paper["id"],
        "Explain this passage",
        selected_text="This MVP1 conversion stores a Markdown representation that can be chunked.",
    )

    assert "Selected passage focus:" in answer["answer"]
    assert answer["retrieval"]["selected_text_preview"].startswith("This MVP1 conversion")
    assert answer["citations"]


def test_chat_can_use_codex_answer_mode(service: PaperService, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paper = service.ingest_paper("2201.08239")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="Codex answer [chunk:1]", stderr="progress")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    answer = service.ask(
        paper["id"],
        "Explain the contribution",
        selected_text="selected context",
        answer_mode="codex",
        codex_options={
            "enabled": True,
            "cli_path": "codex",
            "timeout_seconds": 5,
            "sandbox": "read-only",
            "cwd": tmp_path,
        },
    )

    command = captured["command"]
    assert answer["answer"] == "Codex answer [chunk:1]"
    assert answer["retrieval"]["provider"] == "codex"
    assert answer["retrieval"]["answer_mode"] == "codex"
    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--skip-git-repo-check" in command


def test_codex_answer_mode_requires_explicit_enablement(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")

    with pytest.raises(ValueError, match="OPEN_ALPHAXIV_CODEX_ENABLED"):
        service.ask(paper["id"], "Use Codex", answer_mode="codex", codex_options={"enabled": False})


def test_codex_timeout_raises_runtime_error(
    service: PaperService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        raise subprocess.TimeoutExpired(cmd=command, timeout=5)

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="timed out after 5 seconds"):
        service.ask(
            paper["id"],
            "Use Codex",
            answer_mode="codex",
            codex_options={"enabled": True, "timeout_seconds": 5, "cwd": tmp_path},
        )


def test_codex_nonzero_returncode_raises_runtime_error(
    service: PaperService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="codex auth failed")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="codex auth failed"):
        service.ask(
            paper["id"],
            "Use Codex",
            answer_mode="codex",
            codex_options={"enabled": True, "cwd": tmp_path},
        )


def test_codex_empty_stdout_raises_runtime_error(
    service: PaperService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="empty answer"):
        service.ask(
            paper["id"],
            "Use Codex",
            answer_mode="codex",
            codex_options={"enabled": True, "cwd": tmp_path},
        )


def test_codex_prompt_states_when_no_chunks_are_available() -> None:
    prompt = build_codex_paper_prompt(
        {"title": "Sparse paper", "arxiv_id": "2601.00001", "authors": ["Test Author"]},
        "What can we infer?",
        [],
        "",
    )

    assert "Retrieved chunks:" in prompt
    assert "(No retrieved chunks available for this paper.)" in prompt


def test_bookmark_tags_and_export(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    updated = service.update_bookmark(paper["id"], True)
    tagged = service.update_tags(paper["id"], ["rag", "graphs", "rag"])
    exported = service.export_markdown(paper["id"])

    assert updated["bookmarked"] is True
    assert tagged["tags"] == ["graphs", "rag"]
    assert "# " in exported
    assert "Literature Graph Snapshot" in exported
