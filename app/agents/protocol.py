from __future__ import annotations

from typing import TypedDict


class AgentRunResult(TypedDict):
    ok: bool
    text: str
    adapter: str
    binary_path: str
    latency_ms: int
    exit_code: int
    stderr_preview: str
    model: str
