from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_path: Path
    storage_dir: Path
    cors_origin: str
    app_env: str
    codex_enabled: bool
    codex_cli_path: str
    codex_model: str
    codex_timeout_seconds: int
    codex_sandbox: str
    codex_home: str
    claude_enabled: bool
    claude_cli_path: str
    claude_timeout_seconds: int
    opencode_enabled: bool
    opencode_cli_path: str
    opencode_model: str
    opencode_timeout_seconds: int
    arxiv_categories: str
    semantic_scholar_api_key: str
    feed_min_interval_seconds: int


def get_settings() -> Settings:
    storage_dir = Path(os.environ.get("OPEN_ALPHAXIV_STORAGE_DIR", "data")).resolve()
    database_path = Path(
        os.environ.get("OPEN_ALPHAXIV_DATABASE_PATH", storage_dir / "open_alphaxiv.db")
    ).resolve()
    timeout_raw = os.environ.get("OPEN_ALPHAXIV_CODEX_TIMEOUT_SECONDS", "180")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = 180
    claude_timeout_raw = os.environ.get("OPEN_ALPHAXIV_CLAUDE_TIMEOUT_SECONDS", "180")
    try:
        claude_timeout_seconds = int(claude_timeout_raw)
    except ValueError:
        claude_timeout_seconds = 180
    opencode_timeout_raw = os.environ.get("OPEN_ALPHAXIV_OPENCODE_TIMEOUT_SECONDS", "180")
    try:
        opencode_timeout_seconds = int(opencode_timeout_raw)
    except ValueError:
        opencode_timeout_seconds = 180
    return Settings(
        database_path=database_path,
        storage_dir=storage_dir,
        cors_origin=os.environ.get("OPEN_ALPHAXIV_CORS_ORIGIN", "http://localhost:3000"),
        app_env=os.environ.get("OPEN_ALPHAXIV_ENV", "local"),
        codex_enabled=os.environ.get("OPEN_ALPHAXIV_CODEX_ENABLED", "").lower() in {"1", "true", "yes"},
        codex_cli_path=os.environ.get("OPEN_ALPHAXIV_CODEX_CLI_PATH", "codex"),
        codex_model=os.environ.get("OPEN_ALPHAXIV_CODEX_MODEL", ""),
        codex_timeout_seconds=timeout_seconds,
        codex_sandbox=os.environ.get("OPEN_ALPHAXIV_CODEX_SANDBOX", "read-only"),
        codex_home=os.environ.get("CODEX_HOME", ""),
        claude_enabled=os.environ.get("OPEN_ALPHAXIV_CLAUDE_ENABLED", "").lower() in {"1", "true", "yes"},
        claude_cli_path=os.environ.get("OPEN_ALPHAXIV_CLAUDE_CLI_PATH", "claude"),
        claude_timeout_seconds=claude_timeout_seconds,
        opencode_enabled=os.environ.get("OPEN_ALPHAXIV_OPENCODE_ENABLED", "").lower() in {"1", "true", "yes"},
        opencode_cli_path=os.environ.get("OPEN_ALPHAXIV_OPENCODE_CLI_PATH", "opencode"),
        opencode_model=os.environ.get("OPEN_ALPHAXIV_OPENCODE_MODEL", ""),
        opencode_timeout_seconds=opencode_timeout_seconds,
        arxiv_categories=os.environ.get("OPEN_ALPHAXIV_ARXIV_CATEGORIES", "cs.LG"),
        semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        feed_min_interval_seconds=_int_env("OPEN_ALPHAXIV_FEED_MIN_INTERVAL_SECONDS", 900),
    )
