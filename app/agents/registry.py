from __future__ import annotations

from typing import Any

from .codex import codex_credentials_available, resolve_executable


def probe_codex(settings: Any, options: dict[str, Any]) -> dict[str, Any]:
    cli_path = resolve_executable(settings.codex_cli_path)
    credentials = codex_credentials_available(options)
    available = bool(settings.codex_enabled and cli_path and credentials)
    if not settings.codex_enabled:
        reason = "Set OPEN_ALPHAXIV_CODEX_ENABLED=true to use Codex paper chat."
    elif not cli_path:
        reason = f"Codex CLI not found: {settings.codex_cli_path}"
    elif not credentials:
        reason = "Codex credentials were not detected for this backend process."
    else:
        reason = "Codex CLI is ready for paper chat."
    return {"available": available, "reason": reason}


def probe_claude_cli(settings: Any) -> dict[str, Any]:
    cli_path = resolve_executable(settings.claude_cli_path)
    available = bool(settings.claude_enabled and cli_path)
    if not settings.claude_enabled:
        reason = "Set OPEN_ALPHAXIV_CLAUDE_ENABLED=true to use Claude Code paper chat."
    elif not cli_path:
        reason = f"Claude Code CLI not found: {settings.claude_cli_path}"
    else:
        reason = "Claude Code CLI is ready for paper chat."
    return {"available": available, "reason": reason}


def probe_opencode(settings: Any) -> dict[str, Any]:
    cli_path = resolve_executable(settings.opencode_cli_path)
    available = bool(settings.opencode_enabled and cli_path)
    if not settings.opencode_enabled:
        reason = "Set OPEN_ALPHAXIV_OPENCODE_ENABLED=true to use OpenCode paper chat."
    elif not cli_path:
        reason = f"OpenCode CLI not found: {settings.opencode_cli_path}"
    else:
        reason = "OpenCode CLI is ready for paper chat."
    return {"available": available, "reason": reason}


def probe_openai_compatible(providers: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        row
        for row in providers
        if row.get("provider_type") == "openai_compatible" and row.get("base_url")
    ]
    if not rows:
        return {
            "available": False,
            "reason": "Create an openai_compatible provider with a base_url, then run healthcheck.",
        }
    healthy = [row for row in rows if row.get("health_status") != "failed"]
    if not healthy:
        return {
            "available": False,
            "reason": "OpenAI-compatible provider healthcheck failed. Fix base_url or API key and re-run healthcheck.",
        }
    return {
        "available": True,
        "reason": "OpenAI-compatible provider is configured for paper chat.",
    }


def collect_agent_status(
    settings: Any,
    *,
    providers: list[dict[str, Any]],
    codex_options: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "codex": probe_codex(settings, codex_options),
        "claude_cli": probe_claude_cli(settings),
        "opencode": probe_opencode(settings),
        "openai_compatible": probe_openai_compatible(providers),
    }
