from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    provider_kind TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    base_url TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL,
                    wire_api TEXT NOT NULL,
                    api_key TEXT NOT NULL DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    health_status TEXT NOT NULL DEFAULT 'unknown',
                    last_checked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    arxiv_id TEXT,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    published_at TEXT,
                    pdf_url TEXT NOT NULL DEFAULT '',
                    landing_url TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    status_reason TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    bookmarked INTEGER NOT NULL DEFAULT 0,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source_type, source_id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    artifact_type TEXT NOT NULL,
                    storage_uri TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    section_path TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entity_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    score REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS paper_graph_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    source_node_type TEXT NOT NULL,
                    source_node_id INTEGER NOT NULL,
                    target_node_type TEXT NOT NULL,
                    target_node_id INTEGER NOT NULL,
                    edge_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    supporting_chunk_ids_json TEXT NOT NULL,
                    description TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS literature_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    external_source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors_json TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    venue TEXT NOT NULL DEFAULT '',
                    abstract TEXT NOT NULL DEFAULT '',
                    citation_count INTEGER NOT NULL DEFAULT 0,
                    group_name TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS literature_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                    source_node_id INTEGER NOT NULL,
                    target_node_id INTEGER NOT NULL,
                    edge_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    explanation TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active',
                    goal TEXT NOT NULL DEFAULT '',
                    current_state TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    current_answer TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    body_markdown TEXT NOT NULL DEFAULT '',
                    note_type TEXT NOT NULL DEFAULT 'idea',
                    status TEXT NOT NULL DEFAULT 'active',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiment_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'planned',
                    hypothesis TEXT NOT NULL DEFAULT '',
                    dataset TEXT NOT NULL DEFAULT '',
                    code_ref TEXT NOT NULL DEFAULT '',
                    command TEXT NOT NULL DEFAULT '',
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    summary TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiment_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES experiment_runs(id) ON DELETE CASCADE,
                    artifact_type TEXT NOT NULL DEFAULT 'other',
                    uri TEXT NOT NULL DEFAULT '',
                    label TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_discussions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_discussion_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discussion_id INTEGER NOT NULL REFERENCES research_discussions(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS grounding_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
                    discussion_message_id INTEGER,
                    title TEXT NOT NULL,
                    content_markdown TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS research_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES research_projects(id) ON DELETE CASCADE,
                    note_id INTEGER REFERENCES research_notes(id) ON DELETE CASCADE,
                    discussion_message_id INTEGER,
                    link_type TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_id TEXT NOT NULL DEFAULT '',
                    target_uri TEXT NOT NULL DEFAULT '',
                    label TEXT NOT NULL DEFAULT '',
                    quote TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    CHECK (note_id IS NOT NULL OR discussion_message_id IS NOT NULL)
                );
                """
            )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            return int(cur.lastrowid)

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)
