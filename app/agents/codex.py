from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from .protocol import AgentRunResult


def resolve_executable(path: str) -> str:
    if "/" in path:
        return path if Path(path).exists() else ""
    return shutil.which(path) or ""


def codex_credentials_available(options: dict[str, Any]) -> bool:
    if os.environ.get("CODEX_ACCESS_TOKEN") or os.environ.get("CODEX_API_KEY"):
        return True
    auth_json_path = os.environ.get("CODEX_AUTH_JSON_PATH")
    if auth_json_path and Path(auth_json_path).exists():
        return True
    codex_home = str(options.get("codex_home") or os.environ.get("CODEX_HOME") or "")
    if codex_home and (Path(codex_home) / "auth.json").exists():
        return True
    return (Path.home() / ".codex" / "auth.json").exists()


def _stderr_preview(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[-500:]


def _prepare_codex_exec(options: dict[str, Any], disabled_message: str) -> dict[str, Any]:
    if not options.get("enabled"):
        raise ValueError(disabled_message)
    cli_path = str(options.get("cli_path") or "codex")
    resolved_cli = resolve_executable(cli_path)
    if not resolved_cli:
        raise ValueError(f"Codex CLI not found: {cli_path}")
    if not codex_credentials_available(options):
        raise ValueError("Codex credentials were not detected for this backend process.")
    timeout_seconds = int(options.get("timeout_seconds") or 180)
    sandbox = str(options.get("sandbox") or "read-only")
    if sandbox not in {"read-only", "workspace-write", "danger-full-access"}:
        sandbox = "read-only"
    env = os.environ.copy()
    codex_home = str(options.get("codex_home") or "")
    if codex_home:
        env["CODEX_HOME"] = codex_home
    return {
        "resolved_cli": resolved_cli,
        "timeout_seconds": timeout_seconds,
        "sandbox": sandbox,
        "model": str(options.get("model") or ""),
        "env": env,
    }


def _run_codex_exec_prompt(
    prompt: str,
    options: dict[str, Any],
    disabled_message: str,
    failure_label: str,
) -> tuple[str, dict[str, Any]]:
    prepared = _prepare_codex_exec(options, disabled_message)
    command = [
        prepared["resolved_cli"],
        "exec",
        "--ephemeral",
        "--sandbox",
        prepared["sandbox"],
        "--skip-git-repo-check",
    ]
    if prepared["model"]:
        command.extend(["--model", prepared["model"]])
    command.append(prompt)
    explicit_cwd = options.get("cwd")
    try:
        if explicit_cwd:
            result = subprocess.run(
                command,
                cwd=str(explicit_cwd),
                capture_output=True,
                text=True,
                timeout=prepared["timeout_seconds"],
                env=prepared["env"],
            )
        else:
            with tempfile.TemporaryDirectory(prefix="open-alphaxiv-codex-") as codex_cwd:
                result = subprocess.run(
                    command,
                    cwd=codex_cwd,
                    capture_output=True,
                    text=True,
                    timeout=prepared["timeout_seconds"],
                    env=prepared["env"],
                )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{failure_label} timed out after {prepared['timeout_seconds']} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"{failure_label} could not start: {exc}") from exc
    if result.returncode != 0:
        stderr = _stderr_preview(result.stderr)
        raise RuntimeError(f"{failure_label} failed: {stderr or 'codex exec exited with an error'}")
    answer = result.stdout.strip()
    if not answer:
        raise RuntimeError(f"{failure_label} returned an empty answer.")
    return answer, {
        "codex_sandbox": prepared["sandbox"],
        "codex_cli_path": prepared["resolved_cli"],
        "codex_stderr_preview": _stderr_preview(result.stderr),
        "model": prepared["model"] or "codex-local-agent",
    }


def run_codex_exec(
    prompt: str,
    options: dict[str, Any],
    disabled_message: str,
    failure_label: str,
) -> AgentRunResult:
    started = time.monotonic()
    text, metadata = _run_codex_exec_prompt(prompt, options, disabled_message, failure_label)
    return {
        "ok": True,
        "text": text,
        "adapter": "codex",
        "binary_path": str(metadata["codex_cli_path"]),
        "latency_ms": int((time.monotonic() - started) * 1000),
        "exit_code": 0,
        "stderr_preview": str(metadata["codex_stderr_preview"]),
        "model": str(metadata["model"]),
    }
