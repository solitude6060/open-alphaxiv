from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import subprocess
import textwrap
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from .store import Store, dumps, loads, utcnow


ARXIV_RE = re.compile(r"(?P<id>\d{4}\.\d{4,5})(v\d+)?")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "paper",
    "using",
    "between",
    "about",
    "have",
    "has",
    "are",
    "was",
    "were",
    "our",
    "their",
}


def normalize_arxiv_id(source: str) -> str:
    match = ARXIV_RE.search(source)
    if not match:
        raise ValueError("Expected an arXiv identifier such as 2201.08239")
    return match.group("id")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch_text(url: str, timeout: float = 8.0) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "open-alphaxiv-mvp1/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read(500_000)
        return content.decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def arxiv_metadata(arxiv_id: str) -> dict[str, Any]:
    feed = fetch_text(f"https://export.arxiv.org/api/query?id_list={arxiv_id}")
    if not feed:
        return fallback_metadata(arxiv_id)
    entry_match = re.search(r"<entry>(.*?)</entry>", feed, re.S)
    entry = entry_match.group(1) if entry_match else feed
    title = _xml_text(entry, "title")
    summary = _xml_text(entry, "summary")
    authors = re.findall(r"<author>\s*<name>(.*?)</name>\s*</author>", entry, re.S)
    published = _xml_text(entry, "published")
    if not title or title.lower() == "arxiv query:":
        return fallback_metadata(arxiv_id)
    return {
        "title": clean_ws(title),
        "abstract": clean_ws(summary) or f"arXiv paper {arxiv_id}",
        "authors": [clean_ws(author) for author in authors] or ["Unknown"],
        "published_at": published,
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def fallback_metadata(arxiv_id: str) -> dict[str, Any]:
    return {
        "title": f"arXiv paper {arxiv_id}",
        "abstract": (
            "Metadata could not be fetched in the current environment. "
            "This local fallback keeps the ingestion, retrieval, and graph workflow testable."
        ),
        "authors": ["Unknown"],
        "published_at": "",
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
        "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def _xml_text(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return clean_ws(match.group(1)) if match else ""


def clean_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("&amp;", "&")).strip()


def build_markdown(meta: dict[str, Any], arxiv_id: str) -> str:
    return textwrap.dedent(
        f"""
        # {meta['title']}

        Source: arXiv:{arxiv_id}

        Authors: {', '.join(meta['authors'])}

        ## Abstract

        {meta['abstract']}

        ## Local Reading Notes

        This MVP1 conversion stores a Markdown representation that can be chunked,
        embedded, searched, cited, and exported. A later converter can replace this
        fallback with full PDF extraction while preserving the same storage contract.

        ## Method Signals

        The paper should be inspected for problem statement, assumptions, method,
        experiments, limitations, citations, and implementation clues.

        ## Retrieval Checklist

        Questions should be answered from retrieved chunks. Every generated answer
        must include chunk citations so the user can audit the source context.
        """
    ).strip()


def chunk_markdown(markdown: str, max_words: int = 120) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    section = "Document"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        words = " ".join(buffer).split()
        while words:
            part = words[:max_words]
            words = words[max_words:]
            text = " ".join(part).strip()
            if text:
                chunks.append(
                    {
                        "section_path": section,
                        "chunk_index": len(chunks),
                        "text": text,
                        "token_count": len(part),
                    }
                )
        buffer = []

    for line in markdown.splitlines():
        if line.startswith("#"):
            flush()
            section = line.lstrip("#").strip() or "Document"
        else:
            buffer.append(line)
    flush()
    return chunks


def embedding(text: str, dimensions: int = 64) -> list[float]:
    vec = [0.0] * dimensions
    for token in WORD_RE.findall(text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
        idx = int.from_bytes(digest, "big") % dimensions
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def extract_entities(text: str, limit: int = 16) -> list[tuple[str, float]]:
    words = [w.lower() for w in WORD_RE.findall(text) if w.lower() not in STOPWORDS]
    counts = Counter(words)
    return [(word, float(score)) for word, score in counts.most_common(limit)]


class PaperService:
    def __init__(self, store: Store, storage_dir: Path):
        self.store = store
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_provider(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        provider_id = self.store.execute(
            """
            INSERT INTO providers
                (name, provider_kind, provider_type, base_url, model, wire_api, api_key,
                 is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("name", "Mock provider"),
                payload.get("provider_kind", "generation"),
                payload.get("provider_type", "mock"),
                payload.get("base_url", ""),
                payload.get("model", "mock-research-model"),
                payload.get("wire_api", "chat_completions"),
                payload.get("api_key", ""),
                1 if payload.get("is_default", True) else 0,
                now,
                now,
            ),
        )
        if payload.get("is_default", True):
            self.store.execute("UPDATE providers SET is_default = 0 WHERE id != ?", (provider_id,))
        return self.get_provider(provider_id)

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            redact_provider(row)
            for row in self.store.query_all("SELECT * FROM providers ORDER BY id DESC")
        ]

    def get_provider(self, provider_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM providers WHERE id = ?", (provider_id,))
        if not row:
            raise KeyError("provider not found")
        return redact_provider(row)

    def healthcheck_provider(self, provider_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM providers WHERE id = ?", (provider_id,))
        if not row:
            raise KeyError("provider not found")
        status = "ok"
        reason = "mock provider is always available"
        if row["provider_type"] != "mock" and not row["base_url"]:
            status = "failed"
            reason = "base_url is required for non-mock providers"
        now = utcnow()
        self.store.execute(
            "UPDATE providers SET health_status = ?, last_checked_at = ?, updated_at = ? WHERE id = ?",
            (status, now, now, provider_id),
        )
        return {"provider_id": provider_id, "status": status, "reason": reason, "checked_at": now}

    def ingest_paper(self, source: str) -> dict[str, Any]:
        arxiv_id = normalize_arxiv_id(source)
        existing = self.store.query_one(
            "SELECT id FROM papers WHERE source_type = 'arxiv' AND source_id = ?", (arxiv_id,)
        )
        if existing:
            return self.get_paper(existing["id"])

        meta = arxiv_metadata(arxiv_id)
        now = utcnow()
        paper_id = self.store.execute(
            """
            INSERT INTO papers
                (source_type, source_id, arxiv_id, title, abstract, authors_json,
                 published_at, pdf_url, landing_url, status, summary, created_at, updated_at)
            VALUES ('arxiv', ?, ?, ?, ?, ?, ?, ?, ?, 'indexing', ?, ?, ?)
            """,
            (
                arxiv_id,
                arxiv_id,
                meta["title"],
                meta["abstract"],
                dumps(meta["authors"]),
                meta["published_at"],
                meta["pdf_url"],
                meta["landing_url"],
                summarize(meta["title"], meta["abstract"]),
                now,
                now,
            ),
        )
        markdown = build_markdown(meta, arxiv_id)
        paper_dir = self.storage_dir / "papers" / str(paper_id)
        paper_dir.mkdir(parents=True, exist_ok=True)
        markdown_path = paper_dir / "paper.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        self.store.execute(
            """
            INSERT INTO artifacts
                (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
            VALUES (?, 'markdown', ?, ?, '{}', ?)
            """,
            (paper_id, str(markdown_path), sha256_text(markdown), now),
        )
        for chunk in chunk_markdown(markdown):
            text = chunk["text"]
            self.store.execute(
                """
                INSERT INTO chunks
                    (paper_id, section_path, chunk_index, text, token_count, embedding_json, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    chunk["section_path"],
                    chunk["chunk_index"],
                    text,
                    chunk["token_count"],
                    dumps(embedding(text)),
                    sha256_text(text),
                ),
            )
        self._build_paper_graph(paper_id, markdown)
        self.build_literature_graph(paper_id)
        self.store.execute(
            "UPDATE papers SET status = 'ready', status_reason = '', updated_at = ? WHERE id = ?",
            (utcnow(), paper_id),
        )
        return self.get_paper(paper_id)

    def _build_paper_graph(self, paper_id: int, markdown: str) -> None:
        chunk_rows = self.store.query_all("SELECT id, text FROM chunks WHERE paper_id = ?", (paper_id,))
        entity_ids: dict[str, int] = {}
        for name, score in extract_entities(markdown):
            entity_id = self.store.execute(
                """
                INSERT INTO entity_nodes
                    (paper_id, name, normalized_name, entity_type, description, score)
                VALUES (?, ?, ?, 'term', ?, ?)
                """,
                (paper_id, name, name.lower(), f"Frequent term extracted from paper text: {name}", score),
            )
            entity_ids[name] = entity_id
        for chunk in chunk_rows:
            for name, score in extract_entities(chunk["text"], limit=6):
                entity_id = entity_ids.get(name)
                if entity_id:
                    self.store.execute(
                        """
                        INSERT INTO paper_graph_edges
                            (paper_id, source_node_type, source_node_id, target_node_type,
                             target_node_id, edge_type, score, supporting_chunk_ids_json, description)
                        VALUES (?, 'entity', ?, 'chunk', ?, 'mentions', ?, ?, ?)
                        """,
                        (
                            paper_id,
                            entity_id,
                            chunk["id"],
                            min(score, 5.0),
                            dumps([chunk["id"]]),
                            f"Chunk mentions extracted term '{name}'.",
                        ),
                    )

    def list_papers(self, query: str = "") -> list[dict[str, Any]]:
        if query:
            needle = f"%{query.lower()}%"
            rows = self.store.query_all(
                """
                SELECT * FROM papers
                WHERE lower(title) LIKE ? OR lower(abstract) LIKE ? OR lower(tags_json) LIKE ?
                ORDER BY id DESC
                """,
                (needle, needle, needle),
            )
        else:
            rows = self.store.query_all("SELECT * FROM papers ORDER BY id DESC")
        return [paper_row(row) for row in rows]

    def get_paper(self, paper_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not row:
            raise KeyError("paper not found")
        paper = paper_row(row)
        paper["chunk_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM chunks WHERE paper_id = ?", (paper_id,)
        )["count"]
        return paper

    def chunks(self, paper_id: int) -> list[dict[str, Any]]:
        return self.store.query_all(
            "SELECT id, section_path, chunk_index, text, token_count FROM chunks WHERE paper_id = ? ORDER BY chunk_index",
            (paper_id,),
        )

    def update_bookmark(self, paper_id: int, bookmarked: bool) -> dict[str, Any]:
        self.store.execute(
            "UPDATE papers SET bookmarked = ?, updated_at = ? WHERE id = ?",
            (1 if bookmarked else 0, utcnow(), paper_id),
        )
        return self.get_paper(paper_id)

    def update_tags(self, paper_id: int, tags: list[str]) -> dict[str, Any]:
        clean_tags = sorted({tag.strip() for tag in tags if tag.strip()})
        self.store.execute(
            "UPDATE papers SET tags_json = ?, updated_at = ? WHERE id = ?",
            (dumps(clean_tags), utcnow(), paper_id),
        )
        return self.get_paper(paper_id)

    def create_chat_session(self, paper_id: int, title: str = "Paper chat") -> dict[str, Any]:
        session_id = self.store.execute(
            "INSERT INTO chat_sessions (paper_id, title, created_at) VALUES (?, ?, ?)",
            (paper_id, title, utcnow()),
        )
        return {"id": session_id, "paper_id": paper_id, "title": title}

    def ask(
        self,
        paper_id: int,
        query: str,
        session_id: int | None = None,
        selected_text: str = "",
        answer_mode: str = "mock",
        codex_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if session_id is None:
            session_id = self.create_chat_session(paper_id)["id"]
        selected_text = clean_ws(selected_text)[:1800]
        retrieval_query = f"{query}\n\nSelected passage:\n{selected_text}" if selected_text else query
        user_message_id = self.store.execute(
            "INSERT INTO chat_messages (session_id, role, content, metadata_json, created_at) VALUES (?, 'user', ?, '{}', ?)",
            (session_id, query, utcnow()),
        )
        ranked = self.retrieve(paper_id, retrieval_query)
        provider = "mock"
        model = "mvp1-cited-extractive"
        run_metadata: dict[str, Any] = {}
        if answer_mode == "codex":
            paper = self.get_paper(paper_id)
            answer, run_metadata = codex_answer(paper, query, ranked, selected_text, codex_options or {})
            provider = "codex"
            model = run_metadata.get("model") or "codex-local-agent"
        elif answer_mode == "mock":
            answer = mock_answer(query, ranked, selected_text)
        else:
            raise ValueError("answer_mode must be 'mock' or 'codex'")
        metadata = {
            "provider": provider,
            "model": model,
            "answer_mode": answer_mode,
            "retrieved_chunk_ids": [item["id"] for item in ranked],
            "retrieval": ranked,
            "selected_text_preview": selected_text[:240],
            "user_message_id": user_message_id,
            **run_metadata,
        }
        assistant_message_id = self.store.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, metadata_json, created_at)
            VALUES (?, 'assistant', ?, ?, ?)
            """,
            (session_id, answer, dumps(metadata), utcnow()),
        )
        return {
            "session_id": session_id,
            "message_id": assistant_message_id,
            "answer": answer,
            "citations": [
                {
                    "chunk_id": item["id"],
                    "section_path": item["section_path"],
                    "score": item["score"],
                    "text": item["text"],
                }
                for item in ranked
            ],
            "retrieval": metadata,
        }

    def retrieve(self, paper_id: int, query: str, limit: int = 4) -> list[dict[str, Any]]:
        qvec = embedding(query)
        rows = self.store.query_all(
            "SELECT id, section_path, chunk_index, text, embedding_json FROM chunks WHERE paper_id = ?",
            (paper_id,),
        )
        scored = []
        qterms = set(WORD_RE.findall(query.lower()))
        for row in rows:
            vec = loads(row["embedding_json"], [])
            lexical = len(qterms & set(WORD_RE.findall(row["text"].lower()))) / (len(qterms) or 1)
            score = cosine(qvec, vec) + lexical
            scored.append(
                {
                    "id": row["id"],
                    "section_path": row["section_path"],
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "score": round(score, 4),
                }
            )
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    def build_literature_graph(self, paper_id: int) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        existing = self.store.query_one(
            "SELECT COUNT(*) AS count FROM literature_nodes WHERE seed_paper_id = ?", (paper_id,)
        )
        if existing and existing["count"] >= 20:
            return self.literature_graph(paper_id)
        self.store.execute("DELETE FROM literature_edges WHERE seed_paper_id = ?", (paper_id,))
        self.store.execute("DELETE FROM literature_nodes WHERE seed_paper_id = ?", (paper_id,))
        seed_year = 2024
        nodes = [
            ("seed", paper["title"], seed_year, "related", 100, "Local seed paper"),
        ]
        topics = [name for name, _ in extract_entities(paper["title"] + " " + paper["abstract"], 12)]
        if not topics:
            topics = ["retrieval", "graph", "research"]
        for idx in range(1, 25):
            group = "prior" if idx <= 8 else "derivative" if idx <= 16 else "related"
            year = seed_year - (9 - idx) if group == "prior" else seed_year + (idx - 15) if group == "derivative" else seed_year
            topic = topics[idx % len(topics)]
            title = f"{group.title()} work {idx}: {topic} for {paper['arxiv_id'] or paper['source_id']}"
            nodes.append((f"mvp1-{paper_id}-{idx}", title, year, group, 80 - idx, f"Generated {group} node"))
        inserted: list[dict[str, Any]] = []
        for external_id, title, year, group, cites, abstract in nodes:
            node_id = self.store.execute(
                """
                INSERT INTO literature_nodes
                    (seed_paper_id, external_source, external_id, title, authors_json,
                     year, venue, abstract, citation_count, group_name, url)
                VALUES (?, 'mvp1-local', ?, ?, ?, ?, 'Local MVP graph', ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    external_id,
                    title,
                    dumps(["Open AlphaXiv Local"]),
                    year,
                    abstract,
                    cites,
                    group,
                    paper["landing_url"],
                ),
            )
            inserted.append({"id": node_id, "group": group})
        seed_node = inserted[0]["id"]
        for idx, node in enumerate(inserted[1:], start=1):
            edge_type = "cites" if node["group"] == "prior" else "cited_by" if node["group"] == "derivative" else "semantic_similarity"
            score = round(1.0 - (idx * 0.025), 3)
            self.store.execute(
                """
                INSERT INTO literature_edges
                    (seed_paper_id, source_node_id, target_node_id, edge_type, score, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    seed_node if edge_type != "cites" else node["id"],
                    node["id"] if edge_type != "cites" else seed_node,
                    edge_type,
                    score,
                    f"MVP1 deterministic {edge_type} score for local graph validation.",
                ),
            )
        return self.literature_graph(paper_id)

    def literature_graph(self, paper_id: int, view: str = "related") -> dict[str, Any]:
        rows = self.store.query_all(
            "SELECT * FROM literature_nodes WHERE seed_paper_id = ? ORDER BY id", (paper_id,)
        )
        if not rows:
            return self.build_literature_graph(paper_id)
        if view in {"prior", "derivative"}:
            rows = [row for row in rows if row["group_name"] in {view, "related"}]
        edges = self.store.query_all(
            "SELECT * FROM literature_edges WHERE seed_paper_id = ? ORDER BY score DESC", (paper_id,)
        )
        visible = {row["id"] for row in rows}
        return {
            "paper_id": paper_id,
            "view": view,
            "nodes": [
                {
                    "id": row["id"],
                    "external_id": row["external_id"],
                    "title": row["title"],
                    "authors": loads(row["authors_json"], []),
                    "year": row["year"],
                    "group": row["group_name"],
                    "citation_count": row["citation_count"],
                    "url": row["url"],
                }
                for row in rows
            ],
            "edges": [
                {
                    "id": row["id"],
                    "source": row["source_node_id"],
                    "target": row["target_node_id"],
                    "edge_type": row["edge_type"],
                    "score": row["score"],
                    "explanation": row["explanation"],
                }
                for row in edges
                if row["source_node_id"] in visible and row["target_node_id"] in visible
            ],
        }

    def export_markdown(self, paper_id: int) -> str:
        paper = self.get_paper(paper_id)
        chunks = self.chunks(paper_id)
        graph = self.literature_graph(paper_id)
        tags = ", ".join(paper["tags"]) or "none"
        lines = [
            f"# {paper['title']}",
            "",
            f"- Source: {paper['landing_url']}",
            f"- Authors: {', '.join(paper['authors'])}",
            f"- Tags: {tags}",
            f"- Bookmarked: {paper['bookmarked']}",
            "",
            "## Summary",
            "",
            paper["summary"],
            "",
            "## Source Chunks",
            "",
        ]
        for chunk in chunks:
            lines.extend([f"### Chunk {chunk['id']} - {chunk['section_path']}", "", chunk["text"], ""])
        lines.extend(["## Literature Graph Snapshot", ""])
        for node in graph["nodes"][:12]:
            lines.append(f"- [{node['group']}] {node['title']} ({node['year']})")
        return "\n".join(lines).strip() + "\n"


def summarize(title: str, abstract: str) -> str:
    text = abstract.strip()
    if len(text) > 420:
        text = text[:417].rsplit(" ", 1)[0] + "..."
    return f"{title}: {text}"


def mock_answer(query: str, chunks: list[dict[str, Any]], selected_text: str = "") -> str:
    if not chunks:
        return "No indexed context is available for this paper yet."
    evidence = " ".join(chunk["text"] for chunk in chunks[:2])
    excerpt = evidence[:520].rsplit(" ", 1)[0]
    citations = ", ".join(f"[chunk:{chunk['id']}]" for chunk in chunks[:3])
    focus = ""
    if selected_text:
        selected_excerpt = selected_text[:260].rsplit(" ", 1)[0] or selected_text[:260]
        focus = f"Selected passage focus: {selected_excerpt}. "
    return (
        f"{focus}Answer based on local retrieved context: {excerpt}. "
        f"This is an MVP1 extractive response to: '{query}'. Sources: {citations}."
    )


def codex_answer(
    paper: dict[str, Any],
    query: str,
    chunks: list[dict[str, Any]],
    selected_text: str,
    options: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    if not options.get("enabled"):
        raise ValueError("Codex paper chat is disabled. Set OPEN_ALPHAXIV_CODEX_ENABLED=true.")
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
    model = str(options.get("model") or "")
    prompt = build_codex_paper_prompt(paper, query, chunks, selected_text)
    command = [
        resolved_cli,
        "exec",
        "--ephemeral",
        "--sandbox",
        sandbox,
        "--skip-git-repo-check",
    ]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    env = os.environ.copy()
    codex_home = str(options.get("codex_home") or "")
    if codex_home:
        env["CODEX_HOME"] = codex_home
    try:
        result = subprocess.run(
            command,
            cwd=str(options.get("cwd") or Path.cwd()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Codex paper chat timed out after {timeout_seconds} seconds.") from exc
    if result.returncode != 0:
        stderr = clean_ws(result.stderr)[-500:]
        raise RuntimeError(f"Codex paper chat failed: {stderr or 'codex exec exited with an error'}")
    answer = result.stdout.strip()
    if not answer:
        raise RuntimeError("Codex paper chat returned an empty answer.")
    return answer, {
        "codex_sandbox": sandbox,
        "codex_cli_path": resolved_cli,
        "codex_stderr_preview": clean_ws(result.stderr)[-500:],
        "model": model or "codex-local-agent",
    }


def build_codex_paper_prompt(
    paper: dict[str, Any],
    query: str,
    chunks: list[dict[str, Any]],
    selected_text: str,
) -> str:
    chunk_lines = []
    for chunk in chunks[:5]:
        text = clean_ws(chunk["text"])[:1400]
        chunk_lines.append(
            f"[chunk:{chunk['id']}] section={chunk['section_path']} score={chunk['score']}\n{text}"
        )
    selected = clean_ws(selected_text)[:1800] or "(none)"
    return textwrap.dedent(
        f"""
        You are answering a research paper question inside Open AlphaXiv Local.

        Constraints:
        - Use only the paper metadata, selected passage, and retrieved chunks below.
        - Do not edit files, run shell commands, browse the web, or ask for more context.
        - If the evidence is insufficient, say exactly what is missing.
        - Cite evidence with [chunk:<id>] references.
        - Keep the answer concise and technical.

        Paper:
        Title: {paper['title']}
        arXiv: {paper.get('arxiv_id') or paper.get('source_id')}
        Authors: {', '.join(paper.get('authors', []))}

        Selected passage:
        {selected}

        Question:
        {query}

        Retrieved chunks:
        {chr(10).join(chunk_lines)}
        """
    ).strip()


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


def redact_provider(row: dict[str, Any]) -> dict[str, Any]:
    copy = dict(row)
    copy["has_api_key"] = bool(copy.pop("api_key", ""))
    return copy


def paper_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "authors": loads(row.get("authors_json"), []),
        "tags": loads(row.get("tags_json"), []),
        "bookmarked": bool(row.get("bookmarked")),
    }
