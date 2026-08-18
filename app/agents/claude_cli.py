from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from typing import Any

from .codex import resolve_executable
from .protocol import AgentRunResult


def _stderr_preview(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[-500:]


def run_claude_print(prompt: str, options: dict[str, Any]) -> AgentRunResult:
    if not options.get("enabled"):
        raise ValueError("Claude Code CLI paper chat is disabled. Set OPEN_ALPHAXIV_CLAUDE_ENABLED=true.")
    cli_path = str(options.get("cli_path") or "claude")
    resolved_cli = resolve_executable(cli_path)
    if not resolved_cli:
        raise ValueError(f"Claude Code CLI not found: {cli_path}")
    timeout_seconds = int(options.get("timeout_seconds") or 180)
    # Claude Code 2.1 treats --allowedTools as variadic <tools...>. An empty
    # value therefore consumes the prompt argv, and -p then errors with
    # "Input must be provided either through stdin or as a prompt argument".
    # Official headless input is `claude -p "query"` or stdin
    # (https://code.claude.com/docs/en/headless).
    command = [resolved_cli, "-p", "--output-format", "text"]
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="open-alphaxiv-claude-") as cwd:
            result = subprocess.run(
                command,
                cwd=cwd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=os.environ.copy(),
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Claude Code CLI timed out after {timeout_seconds} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Claude Code CLI could not start: {exc}") from exc
    if result.returncode != 0:
        stderr = _stderr_preview(result.stderr)
        raise RuntimeError(f"Claude Code CLI failed: {stderr or 'claude -p exited with an error'}")
    answer = result.stdout.strip()
    if not answer:
        raise RuntimeError("Claude Code CLI returned an empty answer.")
    return {
        "ok": True,
        "text": answer,
        "adapter": "claude_cli",
        "binary_path": resolved_cli,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "exit_code": result.returncode,
        "stderr_preview": _stderr_preview(result.stderr),
        "model": str(options.get("model") or "claude-code-local-agent"),
    }
