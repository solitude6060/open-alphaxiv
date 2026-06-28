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


@pytest.fixture(autouse=True)
def deterministic_pdf_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def pdf_bytes(url: str) -> bytes | None:
        return b"%PDF-1.4 deterministic fixture"

    def pdf_text(path: Path) -> str:
        method_text = " ".join(
            [
                "The model uses scaled dot product attention, multi head attention, feed forward layers,",
                "residual connections, layer normalization, positional encoding, label smoothing,",
                "autoregressive decoding, teacher forcing, beam search, and parallelizable sequence modeling.",
            ]
            * 12
        )
        return (
            "Introduction\n"
            "This paper introduces a transformer architecture with attention and positional encoding.\n\n"
            "Method\n"
            f"{method_text}\n\n"
            "Experiments\n"
            "Machine translation experiments compare BLEU scores against recurrent baselines."
        )

    def page_images(pdf_path: Path, output_dir: Path, max_pages: int = 12) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        page = output_dir / "page-001.png"
        page.write_bytes(b"png")
        return [page]

    monkeypatch.setattr("app.services.fetch_binary", pdf_bytes)
    monkeypatch.setattr("app.services.extract_pdf_text", pdf_text)
    monkeypatch.setattr("app.services.render_pdf_page_images", page_images)


def test_normalize_arxiv_id_from_url() -> None:
    assert normalize_arxiv_id("https://arxiv.org/abs/2201.08239v2") == "2201.08239"


def test_ingest_paper_creates_ready_chunks_and_graph(service: PaperService) -> None:
    paper = service.ingest_paper("https://arxiv.org/abs/2201.08239")

    assert paper["status"] == "ready"
    assert paper["arxiv_id"] == "2201.08239"
    assert paper["chunk_count"] >= 3
    assert paper["full_text_available"] is True
    assert paper["page_image_count"] == 1
    assert len(service.chunks(paper["id"])) >= 3
    full_text = service.paper_text(paper["id"])
    assert "scaled dot product attention" in full_text["text"]
    pages = service.paper_pages(paper["id"])
    assert pages[0]["page_number"] == 1
    assert pages[0]["image_url"].endswith("/api/papers/1/pages/1.png")
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
        selected_image={"page": 1, "x": 10, "y": 12, "width": 40, "height": 20},
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
    prompt = command[-1]
    assert answer["answer"] == "Codex answer [chunk:1]"
    assert answer["retrieval"]["provider"] == "codex"
    assert answer["retrieval"]["answer_mode"] == "codex"
    assert answer["retrieval"]["context_strategy"] == "full_text"
    assert "Paper context:" in prompt
    assert "scaled dot product attention" in prompt
    assert "Selected image region:" in prompt
    assert "Retrieved chunks:" not in prompt
    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--skip-git-repo-check" in command


def test_codex_answer_mode_requires_explicit_enablement(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")

    with pytest.raises(ValueError, match="OPEN_ALPHAXIV_CODEX_ENABLED"):
        service.ask(paper["id"], "Use Codex", answer_mode="codex", codex_options={"enabled": False})


def test_codex_prompt_truncates_long_paper_context() -> None:
    prompt = build_codex_paper_prompt(
        {"title": "Long paper", "arxiv_id": "2601.00001", "authors": ["Test Author"]},
        "What can we infer?",
        "word " * 50_000,
        "",
        None,
    )

    assert "Paper context was truncated" in prompt
    assert len(prompt) < 90_000


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


def test_codex_oserror_raises_runtime_error(
    service: PaperService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        raise PermissionError("permission denied")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="could not start: permission denied"):
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


def test_codex_answer_uses_isolated_default_cwd(
    service: PaperService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        cwd = Path(str(kwargs["cwd"]))
        captured["cwd_name"] = cwd.name
        captured["cwd_exists_during_run"] = cwd.exists()
        return SimpleNamespace(returncode=0, stdout="Codex answer [chunk:1]", stderr="")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    service.ask(
        paper["id"],
        "Use Codex",
        answer_mode="codex",
        codex_options={"enabled": True},
    )

    assert str(captured["cwd_name"]).startswith("open-alphaxiv-codex-")
    assert captured["cwd_exists_during_run"] is True


def test_codex_prompt_states_when_no_text_is_available() -> None:
    prompt = build_codex_paper_prompt(
        {"title": "Sparse paper", "arxiv_id": "2601.00001", "authors": ["Test Author"]},
        "What can we infer?",
        "",
        "",
        None,
    )

    assert "Paper context:" in prompt
    assert "(No extracted paper text is available.)" in prompt


def test_bookmark_tags_and_export(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    updated = service.update_bookmark(paper["id"], True)
    tagged = service.update_tags(paper["id"], ["rag", "graphs", "rag"])
    exported = service.export_markdown(paper["id"])

    assert updated["bookmarked"] is True
    assert tagged["tags"] == ["graphs", "rag"]
    assert "# " in exported
    assert "Literature Graph Snapshot" in exported
