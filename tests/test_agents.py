from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.agents.claude_cli import run_claude_print
from app.agents.codex import run_codex_exec
from app.agents.openai_compatible import chat_completions
from app.agents.opencode import run_opencode
from app.agents.protocol import AgentRunResult


def test_agent_run_result_includes_adapter_name() -> None:
    result: AgentRunResult = {
        "ok": True,
        "text": "hello",
        "adapter": "codex",
        "binary_path": "/usr/bin/codex",
        "latency_ms": 1,
        "exit_code": 0,
        "stderr_preview": "",
        "model": "codex-local-agent",
    }
    assert result["adapter"] == "codex"


def test_run_codex_exec_raises_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.agents.codex.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.agents.codex.codex_credentials_available", lambda options: True)

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="", stderr="auth failed")

    monkeypatch.setattr("app.agents.codex.subprocess.run", fake_run)
    with pytest.raises(RuntimeError, match="auth failed"):
        run_codex_exec(
            "Summarize the paper",
            {
                "enabled": True,
                "cli_path": "codex",
                "timeout_seconds": 5,
                "sandbox": "read-only",
                "cwd": "/tmp",
            },
            "Codex paper chat is disabled.",
            "Codex paper chat",
        )


def test_run_codex_exec_uses_isolated_temp_cwd_when_unspecified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr("app.agents.codex.resolve_executable", lambda path: "/usr/local/bin/codex")
    monkeypatch.setattr("app.agents.codex.codex_credentials_available", lambda options: True)

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.agents.codex.subprocess.run", fake_run)
    result = run_codex_exec(
        "Question",
        {"enabled": True, "cli_path": "codex", "timeout_seconds": 5, "sandbox": "read-only"},
        "disabled",
        "Codex paper chat",
    )
    assert result["ok"] is True
    assert result["text"] == "ok"
    assert result["adapter"] == "codex"
    assert captured["command"][:2] == ["/usr/local/bin/codex", "exec"]
    assert captured["cwd"]
    assert captured["cwd"] != "."


def test_claude_cli_uses_print_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        recorded["command"] = command
        recorded["cwd"] = kwargs.get("cwd")
        recorded["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="cited answer", stderr="")

    monkeypatch.setattr("app.agents.claude_cli.subprocess.run", fake_run)
    monkeypatch.setattr("app.agents.claude_cli.resolve_executable", lambda path: "/bin/claude")

    result = run_claude_print(
        "What is attention?",
        {"enabled": True, "cli_path": "claude", "timeout_seconds": 30},
    )
    command = recorded["command"]
    assert isinstance(command, list)
    assert command == ["/bin/claude", "-p", "--output-format", "text"]
    assert recorded["input"] == "What is attention?"
    assert "--bare" not in command
    assert "--allowedTools" not in command
    assert "--allowed-tools" not in command
    assert result["ok"] is True
    assert result["adapter"] == "claude_cli"
    assert result["text"] == "cited answer"
    assert recorded["cwd"]
    assert recorded["cwd"] != "."


def test_opencode_run_uses_run_subcommand(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        recorded["command"] = command
        recorded["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout="opencode answer", stderr="")

    monkeypatch.setattr("app.agents.opencode.subprocess.run", fake_run)
    monkeypatch.setattr("app.agents.opencode.resolve_executable", lambda path: "/bin/opencode")

    result = run_opencode(
        "What is attention?",
        {"enabled": True, "cli_path": "opencode", "timeout_seconds": 30, "model": "gpt-5.4"},
    )
    command = recorded["command"]
    assert isinstance(command, list)
    assert command[1] == "run"
    assert "--format" in command
    assert "--dir" in command
    assert command[command.index("--dir") + 1] == recorded["cwd"]
    assert "claude-pro-max" not in " ".join(str(part) for part in command)
    assert result["ok"] is True
    assert result["adapter"] == "opencode"
    assert result["text"] == "opencode answer"
    assert "--model" in command
    assert "gpt-5.4" in command
    assert recorded["cwd"]
    assert recorded["cwd"] != "."


def test_openai_compatible_rejects_link_local_http() -> None:
    with pytest.raises(ValueError, match="localhost"):
        chat_completions(
            "http://169.254.169.254/",
            "sk-secret",
            "gpt-4.1",
            [{"role": "user", "content": "hi"}],
            5.0,
        )


def test_openai_compatible_rejects_file_url() -> None:
    with pytest.raises(ValueError, match="http"):
        chat_completions(
            "file:///etc/passwd",
            "sk-secret",
            "gpt-4.1",
            [{"role": "user", "content": "hi"}],
            5.0,
        )


def test_openai_compatible_chat_completions_posts_json_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "grounded answer"}}]}

    def fake_request(method: str, url: str, **kwargs: object) -> FakeResponse:
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        return FakeResponse()

    monkeypatch.setattr("app.agents.openai_compatible.request_json", fake_request)
    text = chat_completions(
        "https://api.openai.com/v1/",
        "sk-secret",
        "gpt-4.1",
        [{"role": "user", "content": "What is attention?"}],
        8.0,
    )
    assert text == "grounded answer"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-secret"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "gpt-4.1"
    assert payload["messages"][0]["content"] == "What is attention?"


def test_openai_compatible_probe_rejects_failed_healthcheck() -> None:
    from app.agents.registry import probe_openai_compatible

    result = probe_openai_compatible(
        [
            {
                "provider_type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "health_status": "failed",
            }
        ]
    )
    assert result["available"] is False
    assert "healthcheck failed" in result["reason"]
