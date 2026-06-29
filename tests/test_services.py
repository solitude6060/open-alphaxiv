from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
from types import SimpleNamespace

import pytest

from app.services import PaperService, build_codex_paper_prompt, extract_pdf_text_layers, normalize_arxiv_id
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

    def text_layers(pdf_path: Path, max_pages: int = 12, timeout: float = 30.0) -> list[dict[str, object]]:
        return [
            {
                "page_number": 1,
                "width": 612.0,
                "height": 792.0,
                "words": [
                    {"text": "Attention", "x": 10.0, "y": 12.0, "width": 8.0, "height": 1.8},
                    {"text": "layers", "x": 18.5, "y": 12.0, "width": 5.0, "height": 1.8},
                ],
            }
        ]

    monkeypatch.setattr("app.services.fetch_binary", pdf_bytes)
    monkeypatch.setattr("app.services.extract_pdf_text", pdf_text)
    monkeypatch.setattr("app.services.render_pdf_page_images", page_images)
    monkeypatch.setattr("app.services.extract_pdf_text_layers", text_layers)


def test_normalize_arxiv_id_from_url() -> None:
    assert normalize_arxiv_id("https://arxiv.org/abs/2201.08239v2") == "2201.08239"


def test_extract_pdf_text_layers_parses_poppler_bbox(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.shutil.which", lambda command: "/usr/bin/pdftotext")

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>'
                '<page width="200" height="100">'
                '<word xMin="20" yMin="10" xMax="60" yMax="20">Hello</word>'
                "</page></doc></body></html>"
            ),
            stderr="",
        )

    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    pages = extract_pdf_text_layers(tmp_path / "paper.pdf")

    assert pages == [
        {
            "page_number": 1,
            "width": 200.0,
            "height": 100.0,
            "words": [{"text": "Hello", "x": 10.0, "y": 10.0, "width": 20.0, "height": 10.0}],
        }
    ]


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
    assert pages[0]["text_layer_url"].endswith("/api/papers/1/pages/1/text")
    text_layers = service.paper_text_layers(paper["id"])
    assert text_layers["pages"][0]["words"][0]["text"] == "Attention"
    text_layer = service.paper_page_text_layer(paper["id"], 1)
    assert text_layer["words"][0]["text"] == "Attention"
    graph = service.literature_graph(paper["id"])
    assert len(graph["nodes"]) >= 20
    assert graph["edges"]


def test_page_text_layers_lazy_generation_is_idempotent(service: PaperService) -> None:
    paper = service.ingest_paper("https://arxiv.org/abs/2201.08239")
    artifact = service.store.query_one(
        "SELECT * FROM artifacts WHERE paper_id = ? AND artifact_type = 'page_text_layers'",
        (paper["id"],),
    )
    assert artifact
    Path(artifact["storage_uri"]).unlink()
    service.store.execute("DELETE FROM artifacts WHERE id = ?", (artifact["id"],))

    first = service.paper_text_layers(paper["id"])
    second = service.paper_text_layers(paper["id"])
    artifact_count = service.store.query_one(
        "SELECT COUNT(*) AS count FROM artifacts WHERE paper_id = ? AND artifact_type = 'page_text_layers'",
        (paper["id"],),
    )["count"]

    assert first["pages"][0]["words"][0]["text"] == "Attention"
    assert second["pages"][0]["words"][0]["text"] == "Attention"
    assert artifact_count == 1


def test_page_text_layer_rejects_unknown_page(service: PaperService) -> None:
    paper = service.ingest_paper("https://arxiv.org/abs/2201.08239")

    with pytest.raises(KeyError, match="page image not found"):
        service.paper_page_text_layer(paper["id"], 999)


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


def test_chat_session_persists_conversation_messages(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    session = service.create_chat_session(paper["id"], "Transformer questions")

    first = service.ask(paper["id"], "What is the paper about?", session_id=session["id"])
    second = service.ask(paper["id"], "What did I ask first?", session_id=session["id"])
    loaded = service.get_chat_session(session["id"])

    assert first["session_id"] == session["id"]
    assert second["session_id"] == session["id"]
    assert [message["role"] for message in loaded["messages"]] == ["user", "assistant", "user", "assistant"]
    assert loaded["messages"][0]["content"] == "What is the paper about?"


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
        system_prompt="Answer in Traditional Chinese and use Markdown bullets.",
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
    assert answer["retrieval"]["system_prompt_chars"] > 0
    assert answer["retrieval"]["system_prompt_preview"].startswith("Answer in Traditional Chinese")
    assert "Paper context:" in prompt
    assert "scaled dot product attention" in prompt
    assert "Selected image region:" in prompt
    assert "User-configured system prompt:" in prompt
    assert "Answer in Traditional Chinese and use Markdown bullets." in prompt
    assert "Retrieved chunks:" not in prompt
    assert command[:2] == ["/usr/local/bin/codex", "exec"]
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--skip-git-repo-check" in command


def test_codex_answer_receives_history_and_whole_paper_scope(
    service: PaperService,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paper = service.ingest_paper("2201.08239")
    session = service.create_chat_session(paper["id"], "Follow-up")
    service.ask(paper["id"], "What is attention?", session_id=session["id"])
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["prompt"] = command[-1]
        return SimpleNamespace(returncode=0, stdout="Codex follow-up answer", stderr="")

    monkeypatch.setattr("app.services.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.services.codex_credentials_available", lambda options: True)
    monkeypatch.setattr("app.services.subprocess.run", fake_run)

    answer = service.ask(
        paper["id"],
        "Continue from the previous question",
        session_id=session["id"],
        answer_mode="codex",
        codex_options={"enabled": True, "timeout_seconds": 5, "cwd": tmp_path},
    )

    prompt = str(captured["prompt"])
    assert answer["retrieval"]["context_scope"] == "whole_paper"
    assert answer["retrieval"]["conversation_message_count"] == 2
    assert "No passage or image region is selected" in prompt
    assert "Conversation history:" in prompt
    assert "user: What is attention?" in prompt
    assert "Paper file references:" in prompt
    assert "Local PDF path:" in prompt


def test_chat_session_rejects_different_paper(service: PaperService) -> None:
    first = service.ingest_paper("2201.08239")
    second = service.ingest_paper("https://arxiv.org/abs/1706.03762")
    session = service.create_chat_session(first["id"], "First paper")

    with pytest.raises(ValueError, match="does not belong"):
        service.ask(second["id"], "Wrong paper", session_id=session["id"])


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


def test_research_project_note_links_and_export(service: PaperService) -> None:
    paper = service.ingest_paper("2201.08239")
    project = service.create_research_project(
        {
            "title": "Transformer reproduction",
            "goal": "Track paper evidence and implementation progress.",
            "current_state": "Reading the attention paper.",
        }
    )
    question = service.create_research_question(
        {
            "project_id": project["id"],
            "question": "Which architectural choices should be reproduced first?",
            "current_answer": "Start with attention and positional encoding.",
        }
    )
    note = service.create_research_note(
        {
            "project_id": project["id"],
            "title": "Attention evidence",
            "body_markdown": "The selected passage motivates the implementation plan.",
            "note_type": "literature_note",
            "tags": ["attention", "implementation"],
        }
    )
    link = service.create_research_link(
        note["id"],
        {
            "link_type": "paper_passage",
            "relation": "supports",
            "target_id": str(paper["id"]),
            "label": paper["title"],
            "quote": "scaled dot product attention",
            "metadata": {"paper_id": paper["id"], "page_number": 3},
        },
    )

    assert project["slug"] == "transformer-reproduction"
    assert project["status"] == "active"
    assert question["status"] == "open"
    assert note["tags"] == ["attention", "implementation"]
    assert link["relation"] == "supports"
    assert link["metadata"]["page_number"] == 3
    assert service.research_note_links(note["id"])[0]["quote"] == "scaled dot product attention"

    exported = service.export_research_project(project["id"])

    assert "# Transformer reproduction" in exported
    assert "## Questions" in exported
    assert "Which architectural choices" in exported
    assert "## Notes" in exported
    assert "[Deterministic test paper 2201.08239, p.3]" in exported
    assert "scaled dot product attention" in exported


def test_paper_passage_and_chat_answer_can_be_captured_as_research_notes(
    service: PaperService,
) -> None:
    paper = service.ingest_paper("2201.08239")
    project = service.create_research_project({"title": "Evidence capture"})
    passage_note = service.create_paper_research_note(
        paper["id"],
        {
            "project_id": project["id"],
            "title": "Selected passage",
            "selected_text": "The model uses scaled dot product attention.",
            "page_number": 2,
        },
    )
    answer = service.ask(paper["id"], "What should I remember?")
    answer_note = service.create_chat_message_research_note(
        answer["message_id"],
        {
            "project_id": project["id"],
            "title": "Assistant takeaway",
        },
    )

    passage_links = service.research_note_links(passage_note["id"])
    answer_links = service.research_note_links(answer_note["id"])

    assert passage_note["body_markdown"].startswith("The model uses scaled dot product attention.")
    assert passage_links[0]["link_type"] == "paper_passage"
    assert passage_links[0]["metadata"]["page_number"] == 2
    assert answer["answer"] in answer_note["body_markdown"]
    assert answer_links[0]["link_type"] == "chat_message"
    assert answer_links[0]["target_id"] == str(answer["message_id"])


def test_research_archive_uses_status_updates(service: PaperService) -> None:
    project = service.create_research_project({"title": "Archive flow"})
    note = service.create_research_note(
        {
            "project_id": project["id"],
            "title": "Temporary note",
            "body_markdown": "Keep this in history.",
        }
    )

    archived_note = service.update_research_note(note["id"], {"status": "archived"})
    archived_project = service.update_research_project(project["id"], {"status": "archived"})

    assert archived_note["status"] == "archived"
    assert archived_project["status"] == "archived"
    assert service.get_research_note(note["id"])["body_markdown"] == "Keep this in history."


def test_research_links_require_note_or_discussion_owner(service: PaperService) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        service.store.execute(
            """
            INSERT INTO research_links
                (project_id, note_id, discussion_message_id, link_type, relation, target_id,
                 target_uri, label, quote, metadata_json, created_at)
            VALUES (NULL, NULL, NULL, 'paper', 'supports', '1', '', '', '', '{}', 'now')
            """
        )


def test_experiment_runs_artifacts_notes_and_export(service: PaperService) -> None:
    project = service.create_research_project({"title": "Experiment tracking"})
    run = service.create_experiment_run(
        {
            "project_id": project["id"],
            "title": "Attention baseline reproduction",
            "hypothesis": "Scaled dot product attention should reproduce the reported BLEU trend.",
            "dataset": "WMT14 en-de",
            "code_ref": "git:abc123",
            "command": "python train.py --config configs/attention.yaml",
            "parameters": {"learning_rate": 0.0003, "seed": 7},
            "metrics": {"bleu": 28.4, "loss": 1.21},
            "summary": "Initial run is below the target score.",
        }
    )
    updated = service.update_experiment_run(
        run["id"],
        {
            "status": "completed",
            "completed_at": "2026-06-30T10:00:00+00:00",
            "metrics": {"bleu": 29.1, "loss": 1.08},
            "summary": "Baseline reproduced within tolerance.",
        },
    )
    artifact = service.create_experiment_artifact(
        run["id"],
        {
            "artifact_type": "metrics",
            "uri": "file:///runs/attention-baseline/metrics.json",
            "label": "Metrics JSON",
            "metadata": {"sha256": "abc123"},
        },
    )
    note = service.create_experiment_research_note(
        run["id"],
        {"project_id": project["id"], "title": "Baseline run summary"},
    )
    artifact_note = service.create_research_note(
        {
            "project_id": project["id"],
            "title": "Artifact note",
            "body_markdown": "Metrics artifact supports the reproduction claim.",
        }
    )
    artifact_link = service.create_research_link(
        artifact_note["id"],
        {
            "link_type": "experiment_artifact",
            "relation": "supports",
            "target_id": str(artifact["id"]),
            "label": artifact["label"],
        },
    )

    assert run["status"] == "planned"
    assert run["parameters"]["seed"] == 7
    assert updated["status"] == "completed"
    assert updated["metrics"]["bleu"] == 29.1
    assert artifact["run_id"] == run["id"]
    assert service.experiment_run_artifacts(run["id"])[0]["uri"].endswith("/metrics.json")
    assert note["note_type"] == "experiment_note"
    assert service.research_note_links(note["id"])[0]["link_type"] == "experiment_run"
    assert artifact_link["link_type"] == "experiment_artifact"

    exported = service.export_research_project(project["id"])

    assert "## Experiment Runs" in exported
    assert "Attention baseline reproduction" in exported
    assert "WMT14 en-de" in exported
    assert "bleu: 29.1" in exported
    assert "Metrics JSON" in exported
    assert "[Experiment run: Attention baseline reproduction]" in exported
    assert "[Experiment artifact: Metrics JSON]" in exported


def test_research_links_validate_experiment_targets(service: PaperService) -> None:
    project = service.create_research_project({"title": "Experiment target validation"})
    note = service.create_research_note(
        {
            "project_id": project["id"],
            "title": "Invalid experiment evidence",
            "body_markdown": "This should not link to missing experiment records.",
        }
    )

    with pytest.raises(KeyError, match="experiment run not found"):
        service.create_research_link(
            note["id"],
            {"link_type": "experiment_run", "relation": "supports", "target_id": "999"},
        )

    with pytest.raises(KeyError, match="experiment artifact not found"):
        service.create_research_link(
            note["id"],
            {"link_type": "experiment_artifact", "relation": "supports", "target_id": "999"},
        )


def test_research_discussions_grounding_snapshots_and_export(service: PaperService) -> None:
    project = service.create_research_project(
        {
            "title": "Grounded research discussion",
            "goal": "Decide whether the experiment supports the paper claim.",
            "current_state": "One baseline run is available.",
        }
    )
    question = service.create_research_question(
        {"project_id": project["id"], "question": "Does the baseline reproduce the claim?"}
    )
    note = service.create_research_note(
        {
            "project_id": project["id"],
            "title": "Paper claim",
            "body_markdown": "The paper claims attention improves translation quality.",
            "note_type": "literature_note",
        }
    )
    run = service.create_experiment_run(
        {
            "project_id": project["id"],
            "title": "Baseline reproduction",
            "dataset": "WMT14 en-de",
            "metrics": {"bleu": 29.1},
            "summary": "The baseline is within tolerance.",
        }
    )
    artifact = service.create_experiment_artifact(
        run["id"],
        {"artifact_type": "metrics", "uri": "file:///runs/baseline/metrics.json", "label": "Metrics"},
    )
    discussion = service.create_research_discussion(
        {"project_id": project["id"], "title": "Interpret baseline result"}
    )
    user_message = service.create_research_discussion_message(
        discussion["id"],
        {"role": "user", "content": "Does the experiment support the paper claim?"},
    )
    assistant_message = service.create_research_discussion_message(
        discussion["id"],
        {"role": "assistant", "content": "It supports the claim within the observed metric tolerance."},
    )
    message_link = service.create_discussion_research_link(
        assistant_message["id"],
        {"link_type": "experiment_run", "relation": "supports", "target_id": str(run["id"])},
    )
    snapshot = service.create_grounding_snapshot(
        project["id"],
        {"title": "Baseline grounding", "discussion_message_id": assistant_message["id"]},
    )

    assert discussion["status"] == "active"
    assert user_message["role"] == "user"
    assert assistant_message["discussion_id"] == discussion["id"]
    assert message_link["discussion_message_id"] == assistant_message["id"]
    assert question["question"] in snapshot["content_markdown"]
    assert note["title"] in snapshot["content_markdown"]
    assert run["title"] in snapshot["content_markdown"]
    assert artifact["label"] in snapshot["content_markdown"]
    assert snapshot["metadata"]["note_count"] == 1
    assert snapshot["metadata"]["experiment_run_count"] == 1

    exported = service.export_research_project(project["id"])

    assert "## Discussions" in exported
    assert "Interpret baseline result" in exported
    assert "## Grounding Snapshots" in exported
    assert "Baseline grounding" in exported
    assert "It supports the claim" in exported


def test_grounding_snapshot_rejects_unknown_project(service: PaperService) -> None:
    with pytest.raises(KeyError, match="research project not found"):
        service.create_grounding_snapshot(999, {"title": "Missing project"})
