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


def run_opencode(prompt: str, options: dict[str, Any]) -> AgentRunResult:
    if not options.get("enabled"):
        raise ValueError("OpenCode paper chat is disabled. Set OPEN_ALPHAXIV_OPENCODE_ENABLED=true.")
    cli_path = str(options.get("cli_path") or "opencode")
    resolved_cli = resolve_executable(cli_path)
    if not resolved_cli:
        raise ValueError(f"OpenCode CLI not found: {cli_path}")
    timeout_seconds = int(options.get("timeout_seconds") or 180)
    model = str(options.get("model") or "")
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="open-alphaxiv-opencode-") as cwd:
            # OpenCode 1.14.50 with only subprocess cwd= and captured stdout
            # returns exit 0 and empty output. --dir makes it emit the answer.
            command = [resolved_cli, "run", "--format", "default", "--dir", cwd]
            if model:
                command.extend(["--model", model])
            command.append(prompt)
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=os.environ.copy(),
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"OpenCode timed out after {timeout_seconds} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"OpenCode could not start: {exc}") from exc
    if result.returncode != 0:
        stderr = _stderr_preview(result.stderr)
        raise RuntimeError(f"OpenCode failed: {stderr or 'opencode run exited with an error'}")
    answer = result.stdout.strip()
    if not answer:
        raise RuntimeError("OpenCode returned an empty answer.")
    return {
        "ok": True,
        "text": answer,
        "adapter": "opencode",
        "binary_path": resolved_cli,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "exit_code": result.returncode,
        "stderr_preview": _stderr_preview(result.stderr),
        "model": model or "opencode-local-agent",
    }
