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


def get_settings() -> Settings:
    storage_dir = Path(os.environ.get("OPEN_ALPHAXIV_STORAGE_DIR", "data")).resolve()
    database_path = Path(
        os.environ.get("OPEN_ALPHAXIV_DATABASE_PATH", storage_dir / "open_alphaxiv.db")
    ).resolve()
    return Settings(
        database_path=database_path,
        storage_dir=storage_dir,
        cors_origin=os.environ.get("OPEN_ALPHAXIV_CORS_ORIGIN", "http://localhost:3000"),
        app_env=os.environ.get("OPEN_ALPHAXIV_ENV", "local"),
    )

