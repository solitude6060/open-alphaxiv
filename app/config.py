from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    )
