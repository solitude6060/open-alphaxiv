from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from threading import Lock
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
MAX_UPLOAD_PDF_BYTES = 50_000_000
PROJECT_STATUSES = {"active", "paused", "completed", "archived"}
QUESTION_STATUSES = {"open", "investigating", "answered", "abandoned"}
NOTE_STATUSES = {"draft", "active", "resolved", "archived"}
NOTE_TYPES = {"idea", "question", "summary", "experiment_note", "decision", "todo", "meeting", "literature_note"}
LINK_TYPES = {
    "paper",
    "paper_passage",
    "paper_region",
    "chat_message",
    "code_path",
    "experiment_run",
    "experiment_artifact",
    "external_url",
}
LINK_RELATIONS = {"supports", "contradicts", "extends", "implements", "cites", "mentions", "questions"}
EXPERIMENT_RUN_STATUSES = {"planned", "running", "completed", "failed", "archived"}
EXPERIMENT_ARTIFACT_TYPES = {"metrics", "checkpoint", "figure", "table", "log", "model", "dataset", "report", "other"}
DISCUSSION_STATUSES = {"active", "archived"}
DISCUSSION_MESSAGE_ROLES = {"user", "assistant", "system"}


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


def fetch_binary(url: str, timeout: float = 20.0, max_bytes: int = 50_000_000) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "open-alphaxiv-mvp1/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read(max_bytes)
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


def search_snippet(*values: Any, query: str = "") -> str:
    texts = [clean_ws(str(value or "")) for value in values if clean_ws(str(value or ""))]
    if not texts:
        return ""
    needle = query.lower()
    for text in texts:
        lower = text.lower()
        if needle and needle in lower:
            start = max(0, lower.find(needle) - 80)
            end = min(len(text), start + 220)
            prefix = "..." if start else ""
            suffix = "..." if end < len(text) else ""
            return f"{prefix}{text[start:end]}{suffix}"
    return texts[0][:220]


def research_search_result(
    result_type: str,
    row: dict[str, Any],
    title: str,
    snippet: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "type": result_type,
        "id": row["id"],
        "project_id": row.get("project_id") or row["id"],
        "title": title,
        "snippet": snippet,
        "created_at": created_at,
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "research-project"


def build_markdown(meta: dict[str, Any], source_label: str, full_text: str = "") -> str:
    body = clean_extracted_text(full_text)
    full_text_section = (
        f"## Full Text\n\n{body}"
        if body
        else textwrap.dedent(
            """
            ## Full Text

            Full text could not be extracted in the current environment. The abstract
            remains available for local reading and question answering.
            """
        ).strip()
    )
    return textwrap.dedent(
        f"""
        # {meta['title']}

        Source: {source_label}

        Authors: {', '.join(meta['authors'])}

        ## Abstract

        {meta['abstract']}

        {full_text_section}
        """
    ).strip()


def upload_title_from_filename(filename: str, fallback: str) -> str:
    stem = Path(filename or "").name
    stem = Path(stem).stem if stem else ""
    title = clean_ws(re.sub(r"[_\-]+", " ", stem))
    return title or fallback


def validate_pdf_bytes(pdf_bytes: bytes) -> None:
    if len(pdf_bytes) > MAX_UPLOAD_PDF_BYTES:
        raise ValueError(upload_size_error_message(MAX_UPLOAD_PDF_BYTES))
    if not pdf_bytes.lstrip().startswith(b"%PDF"):
        raise ValueError("uploaded file must be a PDF")
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
            handle.write(pdf_bytes)
            handle.flush()
            result = subprocess.run(
                [pdfinfo, handle.name],
                capture_output=True,
                text=True,
                timeout=10,
            )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("uploaded file must be a parseable PDF")
    if result.returncode != 0:
        raise ValueError("uploaded file must be a parseable PDF")


def upload_size_error_message(limit_bytes: int) -> str:
    return f"uploaded PDF exceeds {limit_bytes} byte limit"


def clean_extracted_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\x00", "").splitlines()]
    compact: list[str] = []
    blank = False
    for line in lines:
        if line.strip():
            compact.append(line)
            blank = False
        elif not blank:
            compact.append("")
            blank = True
    return "\n".join(compact).strip()


def extract_pdf_text(pdf_path: Path, timeout: float = 30.0) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    try:
        result = subprocess.run(
            [pdftotext, "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return clean_extracted_text(result.stdout)


def render_pdf_page_images(pdf_path: Path, output_dir: Path, max_pages: int = 12) -> list[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    try:
        result = subprocess.run(
            [
                pdftoppm,
                "-png",
                "-r",
                "120",
                "-f",
                "1",
                "-l",
                str(max_pages),
                str(pdf_path),
                str(prefix),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    normalized: list[Path] = []
    for index, path in enumerate(sorted(output_dir.glob("page-*.png")), start=1):
        target = output_dir / f"page-{index:03d}.png"
        if path != target:
            path.replace(target)
        normalized.append(target)
    return normalized


def extract_pdf_text_layers(pdf_path: Path, max_pages: int = 12, timeout: float = 30.0) -> list[dict[str, Any]]:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return []
    try:
        result = subprocess.run(
            [
                pdftotext,
                "-bbox-layout",
                "-f",
                "1",
                "-l",
                str(max_pages),
                str(pdf_path),
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        root = ET.fromstring(result.stdout)
    except ET.ParseError:
        return []
    pages: list[dict[str, Any]] = []
    for page in root.iter():
        if strip_xml_namespace(page.tag) != "page":
            continue
        width = parse_float(page.attrib.get("width"))
        height = parse_float(page.attrib.get("height"))
        words = []
        for word in page.iter():
            if strip_xml_namespace(word.tag) != "word":
                continue
            text = "".join(word.itertext()).strip()
            if not text:
                continue
            x_min = parse_float(word.attrib.get("xMin"))
            y_min = parse_float(word.attrib.get("yMin"))
            x_max = parse_float(word.attrib.get("xMax"))
            y_max = parse_float(word.attrib.get("yMax"))
            if width <= 0 or height <= 0 or x_max <= x_min or y_max <= y_min:
                continue
            words.append(
                {
                    "text": text,
                    "x": round((x_min / width) * 100, 4),
                    "y": round((y_min / height) * 100, 4),
                    "width": round(((x_max - x_min) / width) * 100, 4),
                    "height": round(((y_max - y_min) / height) * 100, 4),
                }
            )
        pages.append(
            {
                "page_number": len(pages) + 1,
                "width": width,
                "height": height,
                "words": words,
            }
        )
    return pages


def strip_xml_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_float(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


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
        self._text_layer_locks: dict[int, Lock] = {}
        self._text_layer_locks_guard = Lock()

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
        paper_dir = self.storage_dir / "papers" / str(paper_id)
        pdf_bytes = fetch_binary(meta["pdf_url"])
        self._index_paper_artifacts(
            paper_id=paper_id,
            paper_dir=paper_dir,
            meta=meta,
            source_label=f"arXiv:{arxiv_id}",
            pdf_bytes=pdf_bytes,
            pdf_metadata={"source": meta["pdf_url"]},
            now=now,
        )
        return self.get_paper(paper_id)

    def ingest_uploaded_pdf(self, filename: str, pdf_bytes: bytes, title: str = "") -> dict[str, Any]:
        validate_pdf_bytes(pdf_bytes)
        source_id = hashlib.sha256(pdf_bytes).hexdigest()
        existing = self.store.query_one(
            "SELECT id FROM papers WHERE source_type = 'upload' AND source_id = ?", (source_id,)
        )
        if existing:
            paper = self.get_paper(existing["id"])
            if paper["status"] == "ready":
                return paper
            self.store.execute("DELETE FROM papers WHERE id = ?", (existing["id"],))

        display_title = clean_ws(title) or upload_title_from_filename(filename, f"Uploaded paper {source_id[:12]}")
        meta = {
            "title": display_title,
            "abstract": (
                "Local PDF uploaded into Open AlphaXiv. Extracted text is stored locally "
                "for reading, search, graph construction, and paper question answering."
            ),
            "authors": ["Local upload"],
            "published_at": "",
            "pdf_url": "",
            "landing_url": "",
        }
        now = utcnow()
        try:
            paper_id = self.store.execute(
                """
                INSERT INTO papers
                    (source_type, source_id, arxiv_id, title, abstract, authors_json,
                     published_at, pdf_url, landing_url, status, summary, created_at, updated_at)
                VALUES ('upload', ?, '', ?, ?, ?, ?, '', '', 'indexing', ?, ?, ?)
                """,
                (
                    source_id,
                    meta["title"],
                    meta["abstract"],
                    dumps(meta["authors"]),
                    meta["published_at"],
                    summarize(meta["title"], meta["abstract"]),
                    now,
                    now,
                ),
            )
        except sqlite3.IntegrityError:
            existing = self.store.query_one(
                "SELECT id FROM papers WHERE source_type = 'upload' AND source_id = ?", (source_id,)
            )
            if existing:
                return self.get_paper(existing["id"])
            raise
        self._index_paper_artifacts(
            paper_id=paper_id,
            paper_dir=self.storage_dir / "papers" / str(paper_id),
            meta=meta,
            source_label=f"upload:{Path(filename or '').name or source_id[:12]}",
            pdf_bytes=pdf_bytes,
            pdf_metadata={"source": "upload", "filename": filename, "content_hash": source_id},
            now=now,
        )
        return self.get_paper(paper_id)

    def _index_paper_artifacts(
        self,
        paper_id: int,
        paper_dir: Path,
        meta: dict[str, Any],
        source_label: str,
        pdf_bytes: bytes | None,
        pdf_metadata: dict[str, Any],
        now: str,
    ) -> None:
        paper_dir.mkdir(parents=True, exist_ok=True)
        full_text = ""
        if pdf_bytes:
            pdf_path = paper_dir / "paper.pdf"
            pdf_path.write_bytes(pdf_bytes)
            self.store.execute(
                """
                INSERT INTO artifacts
                    (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
                VALUES (?, 'pdf', ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    str(pdf_path),
                    hashlib.sha256(pdf_bytes).hexdigest(),
                    dumps(pdf_metadata),
                    now,
                ),
            )
            full_text = extract_pdf_text(pdf_path)
            if full_text:
                text_path = paper_dir / "paper.txt"
                text_path.write_text(full_text, encoding="utf-8")
                self.store.execute(
                    """
                    INSERT INTO artifacts
                        (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
                    VALUES (?, 'pdf_text', ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        str(text_path),
                        sha256_text(full_text),
                        dumps({"source_artifact": "pdf", "extractor": "pdftotext"}),
                        now,
                    ),
                )
            for page_number, image_path in enumerate(
                render_pdf_page_images(pdf_path, paper_dir / "pages"),
                start=1,
            ):
                self.store.execute(
                    """
                    INSERT INTO artifacts
                        (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
                    VALUES (?, 'page_image', ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        str(image_path),
                        hashlib.sha256(image_path.read_bytes()).hexdigest(),
                        dumps({"page_number": page_number, "source_artifact": "pdf"}),
                        now,
                    ),
                )
            text_layers = extract_pdf_text_layers(pdf_path)
            if text_layers:
                text_layer_path = paper_dir / "pages" / "text-layers.json"
                text_layer_json = dumps({"pages": text_layers})
                text_layer_path.write_text(text_layer_json, encoding="utf-8")
                self.store.execute(
                    """
                    INSERT INTO artifacts
                        (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
                    VALUES (?, 'page_text_layers', ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        str(text_layer_path),
                        sha256_text(text_layer_json),
                        dumps({"source_artifact": "pdf", "extractor": "pdftotext-bbox-layout"}),
                        now,
                    ),
                )
        markdown = build_markdown(meta, source_label, full_text)
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
        return [self._with_asset_counts(paper_row(row)) for row in rows]

    def get_paper(self, paper_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM papers WHERE id = ?", (paper_id,))
        if not row:
            raise KeyError("paper not found")
        paper = self._with_asset_counts(paper_row(row))
        paper["chunk_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM chunks WHERE paper_id = ?", (paper_id,)
        )["count"]
        return paper

    def _with_asset_counts(self, paper: dict[str, Any]) -> dict[str, Any]:
        paper_id = paper["id"]
        text_artifact = self.store.query_one(
            "SELECT id FROM artifacts WHERE paper_id = ? AND artifact_type = 'pdf_text' LIMIT 1",
            (paper_id,),
        )
        page_count = self.store.query_one(
            "SELECT COUNT(*) AS count FROM artifacts WHERE paper_id = ? AND artifact_type = 'page_image'",
            (paper_id,),
        )["count"]
        paper["full_text_available"] = bool(text_artifact)
        paper["page_image_count"] = page_count
        return paper

    def paper_text(self, paper_id: int) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        artifact = self.store.query_one(
            """
            SELECT * FROM artifacts
            WHERE paper_id = ? AND artifact_type IN ('pdf_text', 'markdown')
            ORDER BY CASE artifact_type WHEN 'pdf_text' THEN 0 ELSE 1 END, id
            LIMIT 1
            """,
            (paper_id,),
        )
        if not artifact:
            return {
                "paper_id": paper_id,
                "source": "abstract",
                "text": paper["abstract"],
                "character_count": len(paper["abstract"]),
            }
        text = clean_extracted_text(Path(artifact["storage_uri"]).read_text(encoding="utf-8"))
        return {
            "paper_id": paper_id,
            "source": artifact["artifact_type"],
            "text": text,
            "character_count": len(text),
        }

    def paper_pages(self, paper_id: int) -> list[dict[str, Any]]:
        rows = self.store.query_all(
            """
            SELECT * FROM artifacts
            WHERE paper_id = ? AND artifact_type = 'page_image'
            ORDER BY id
            """,
            (paper_id,),
        )
        pages: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            metadata = loads(row.get("metadata_json"), {})
            page_number = int(metadata.get("page_number") or index)
            pages.append(
                {
                    "paper_id": paper_id,
                    "page_number": page_number,
                    "image_url": f"/api/papers/{paper_id}/pages/{page_number}.png",
                    "text_layer_url": f"/api/papers/{paper_id}/pages/{page_number}/text",
                }
            )
        return pages

    def paper_page_image_path(self, paper_id: int, page_number: int) -> Path:
        rows = self.store.query_all(
            """
            SELECT * FROM artifacts
            WHERE paper_id = ? AND artifact_type = 'page_image'
            ORDER BY id
            """,
            (paper_id,),
        )
        for index, row in enumerate(rows, start=1):
            metadata = loads(row.get("metadata_json"), {})
            row_page_number = int(metadata.get("page_number") or index)
            if row_page_number == page_number:
                return Path(row["storage_uri"])
        raise KeyError("page image not found")

    def paper_page_text_layer(self, paper_id: int, page_number: int) -> dict[str, Any]:
        self.paper_page_image_path(paper_id, page_number)
        payload = self.paper_text_layers(paper_id)
        for page in payload.get("pages", []):
            if int(page.get("page_number") or 0) == page_number:
                return {"paper_id": paper_id, **page}
        return {"paper_id": paper_id, "page_number": page_number, "width": 0, "height": 0, "words": []}

    def paper_text_layers(self, paper_id: int) -> dict[str, Any]:
        self.get_paper(paper_id)
        artifact = self._ensure_page_text_layers(paper_id)
        if not artifact:
            return {"paper_id": paper_id, "pages": []}
        try:
            payload = loads(Path(artifact["storage_uri"]).read_text(encoding="utf-8"), {"pages": []})
        except (OSError, ValueError):
            return {"paper_id": paper_id, "pages": []}
        return {"paper_id": paper_id, "pages": payload.get("pages", [])}

    def _page_text_layers_artifact(self, paper_id: int) -> dict[str, Any] | None:
        rows = self.store.query_all(
            """
            SELECT * FROM artifacts
            WHERE paper_id = ? AND artifact_type = 'page_text_layers'
            ORDER BY id
            """,
            (paper_id,),
        )
        for row in rows:
            if Path(row["storage_uri"]).exists():
                return row
        return None

    def _text_layer_lock(self, paper_id: int) -> Lock:
        with self._text_layer_locks_guard:
            if paper_id not in self._text_layer_locks:
                self._text_layer_locks[paper_id] = Lock()
            return self._text_layer_locks[paper_id]

    def _ensure_page_text_layers(self, paper_id: int) -> dict[str, Any] | None:
        artifact = self._page_text_layers_artifact(paper_id)
        if artifact:
            return artifact
        with self._text_layer_lock(paper_id):
            artifact = self._page_text_layers_artifact(paper_id)
            if artifact:
                return artifact
            return self._build_page_text_layers(paper_id)

    def _build_page_text_layers(self, paper_id: int) -> dict[str, Any] | None:
        pdf_artifact = self.store.query_one(
            """
            SELECT * FROM artifacts
            WHERE paper_id = ? AND artifact_type = 'pdf'
            ORDER BY id
            LIMIT 1
            """,
            (paper_id,),
        )
        if not pdf_artifact:
            return None
        pdf_path = Path(pdf_artifact["storage_uri"])
        if not pdf_path.exists():
            return None
        text_layers = extract_pdf_text_layers(pdf_path)
        if not text_layers:
            return None
        text_layer_path = pdf_path.parent / "pages" / "text-layers.json"
        text_layer_path.parent.mkdir(parents=True, exist_ok=True)
        text_layer_json = dumps({"pages": text_layers})
        text_layer_path.write_text(text_layer_json, encoding="utf-8")
        now = utcnow()
        artifact_id = self.store.execute(
            """
            INSERT INTO artifacts
                (paper_id, artifact_type, storage_uri, content_hash, metadata_json, created_at)
            VALUES (?, 'page_text_layers', ?, ?, ?, ?)
            """,
            (
                paper_id,
                str(text_layer_path),
                sha256_text(text_layer_json),
                dumps({"source_artifact": "pdf", "extractor": "pdftotext-bbox-layout"}),
                now,
            ),
        )
        return {
            "id": artifact_id,
            "paper_id": paper_id,
            "artifact_type": "page_text_layers",
            "storage_uri": str(text_layer_path),
            "content_hash": sha256_text(text_layer_json),
            "metadata_json": dumps({"source_artifact": "pdf", "extractor": "pdftotext-bbox-layout"}),
            "created_at": now,
        }

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
        self.get_paper(paper_id)
        now = utcnow()
        session_id = self.store.execute(
            "INSERT INTO chat_sessions (paper_id, title, created_at) VALUES (?, ?, ?)",
            (paper_id, title, now),
        )
        return {"id": session_id, "paper_id": paper_id, "title": title, "created_at": now, "messages": []}

    def list_chat_sessions(self, paper_id: int) -> list[dict[str, Any]]:
        self.get_paper(paper_id)
        return self.store.query_all(
            """
            SELECT
                s.id,
                s.paper_id,
                s.title,
                s.created_at,
                COUNT(m.id) AS message_count,
                MAX(m.created_at) AS latest_message_at
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id
            WHERE s.paper_id = ?
            GROUP BY s.id
            ORDER BY COALESCE(latest_message_at, s.created_at) DESC, s.id DESC
            """,
            (paper_id,),
        )

    def get_chat_session(self, session_id: int) -> dict[str, Any]:
        row = self.store.query_one(
            "SELECT id, paper_id, title, created_at FROM chat_sessions WHERE id = ?",
            (session_id,),
        )
        if not row:
            raise KeyError("chat session not found")
        row["messages"] = self.chat_messages(session_id)
        return row

    def chat_messages(self, session_id: int) -> list[dict[str, Any]]:
        rows = self.store.query_all(
            """
            SELECT id, session_id, role, content, metadata_json, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        )
        messages = []
        for row in rows:
            metadata = loads(row.pop("metadata_json"), {})
            messages.append({**row, "metadata": metadata})
        return messages

    def ask(
        self,
        paper_id: int,
        query: str,
        session_id: int | None = None,
        selected_text: str = "",
        selected_image: dict[str, Any] | None = None,
        system_prompt: str = "",
        answer_mode: str = "mock",
        codex_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if session_id is None:
            session_id = self.create_chat_session(paper_id)["id"]
        else:
            session = self.get_chat_session(session_id)
            if session["paper_id"] != paper_id:
                raise ValueError("chat session does not belong to this paper")
        conversation_history = self.chat_messages(session_id)[-12:]
        selected_text = clean_ws(selected_text)[:1800]
        system_prompt = clean_ws(system_prompt)[:4000]
        context_scope = "selection" if selected_text or selected_image else "whole_paper"
        user_message_id = self.store.execute(
            "INSERT INTO chat_messages (session_id, role, content, metadata_json, created_at) VALUES (?, 'user', ?, '{}', ?)",
            (session_id, query, utcnow()),
        )
        ranked: list[dict[str, Any]] = []
        provider = "mock"
        model = "mvp1-cited-extractive"
        run_metadata: dict[str, Any] = {}
        if answer_mode == "codex":
            paper = self.get_paper(paper_id)
            paper_context = self.paper_text(paper_id)["text"]
            file_references = self.paper_file_references(paper_id, paper)
            answer, run_metadata = codex_answer(
                paper,
                query,
                paper_context,
                selected_text,
                selected_image,
                system_prompt,
                conversation_history,
                file_references,
                codex_options or {},
            )
            provider = "codex"
            model = run_metadata.get("model") or "codex-local-agent"
        elif answer_mode == "mock":
            retrieval_query = f"{query}\n\nSelected passage:\n{selected_text}" if selected_text else query
            ranked = self.retrieve(paper_id, retrieval_query)
            answer = mock_answer(query, ranked, selected_text)
        else:
            raise ValueError("answer_mode must be 'mock' or 'codex'")
        metadata = {
            "provider": provider,
            "model": model,
            "answer_mode": answer_mode,
            "retrieved_chunk_ids": [item["id"] for item in ranked],
            "retrieval": ranked,
            "context_scope": context_scope,
            "selected_text_preview": selected_text[:240],
            "selected_image": selected_image or None,
            "system_prompt_preview": system_prompt[:240] if answer_mode == "codex" else "",
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
            "user_message_id": user_message_id,
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

    def paper_file_references(self, paper_id: int, paper: dict[str, Any] | None = None) -> dict[str, str]:
        paper = paper or self.get_paper(paper_id)
        pdf_artifact = self.store.query_one(
            """
            SELECT storage_uri FROM artifacts
            WHERE paper_id = ? AND artifact_type = 'pdf'
            ORDER BY id DESC
            LIMIT 1
            """,
            (paper_id,),
        )
        return {
            "landing_url": paper.get("landing_url", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "local_pdf_path": pdf_artifact["storage_uri"] if pdf_artifact else "",
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

    def create_research_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = clean_ws(str(payload.get("title") or "Untitled research project"))
        status = self._valid_choice(payload.get("status", "active"), PROJECT_STATUSES, "project status")
        now = utcnow()
        project_id = self.store.execute(
            """
            INSERT INTO research_projects (title, slug, status, goal, current_state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                self._unique_project_slug(str(payload.get("slug") or title)),
                status,
                clean_ws(str(payload.get("goal") or "")),
                clean_ws(str(payload.get("current_state") or "")),
                now,
                now,
            ),
        )
        return self.get_research_project(project_id)

    def list_research_projects(self, status: str = "") -> list[dict[str, Any]]:
        if status:
            rows = self.store.query_all(
                "SELECT * FROM research_projects WHERE status = ? ORDER BY updated_at DESC, id DESC",
                (status,),
            )
        else:
            rows = self.store.query_all("SELECT * FROM research_projects ORDER BY updated_at DESC, id DESC")
        return [research_project_row(row) for row in rows]

    def get_research_project(self, project_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_projects WHERE id = ?", (project_id,))
        if not row:
            raise KeyError("research project not found")
        project = research_project_row(row)
        project["note_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM research_notes WHERE project_id = ?", (project_id,)
        )["count"]
        project["question_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM research_questions WHERE project_id = ?", (project_id,)
        )["count"]
        return project

    def update_research_project(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_research_project(project_id)
        updates: list[str] = []
        values: list[Any] = []
        if "title" in payload:
            updates.append("title = ?")
            values.append(clean_ws(str(payload["title"])))
        if "slug" in payload and payload.get("slug"):
            updates.append("slug = ?")
            values.append(self._unique_project_slug(str(payload["slug"]), project_id))
        if "status" in payload:
            updates.append("status = ?")
            values.append(self._valid_choice(payload["status"], PROJECT_STATUSES, "project status"))
        if "goal" in payload:
            updates.append("goal = ?")
            values.append(clean_ws(str(payload["goal"])))
        if "current_state" in payload:
            updates.append("current_state = ?")
            values.append(clean_ws(str(payload["current_state"])))
        if updates:
            updates.append("updated_at = ?")
            values.append(utcnow())
            values.append(project_id)
            self.store.execute(f"UPDATE research_projects SET {', '.join(updates)} WHERE id = ?", tuple(values))
        return self.get_research_project(project_id)

    def create_research_question(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        status = self._valid_choice(payload.get("status", "open"), QUESTION_STATUSES, "question status")
        now = utcnow()
        question_id = self.store.execute(
            """
            INSERT INTO research_questions
                (project_id, question, status, current_answer, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                clean_ws(str(payload.get("question") or "")),
                status,
                clean_ws(str(payload.get("current_answer") or "")),
                now,
                now,
            ),
        )
        return self.get_research_question(question_id)

    def list_research_questions(self, project_id: int | None = None, status: str = "") -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.store.query_all(
            f"SELECT * FROM research_questions {where} ORDER BY updated_at DESC, id DESC",
            tuple(values),
        )
        return [research_question_row(row) for row in rows]

    def get_research_question(self, question_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_questions WHERE id = ?", (question_id,))
        if not row:
            raise KeyError("research question not found")
        return research_question_row(row)

    def update_research_question(self, question_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_research_question(question_id)
        updates: list[str] = []
        values: list[Any] = []
        if "question" in payload:
            updates.append("question = ?")
            values.append(clean_ws(str(payload["question"])))
        if "status" in payload:
            updates.append("status = ?")
            values.append(self._valid_choice(payload["status"], QUESTION_STATUSES, "question status"))
        if "current_answer" in payload:
            updates.append("current_answer = ?")
            values.append(clean_ws(str(payload["current_answer"])))
        if updates:
            updates.append("updated_at = ?")
            values.append(utcnow())
            values.append(question_id)
            self.store.execute(f"UPDATE research_questions SET {', '.join(updates)} WHERE id = ?", tuple(values))
        return self.get_research_question(question_id)

    def create_research_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        now = utcnow()
        note_id = self.store.execute(
            """
            INSERT INTO research_notes
                (project_id, title, body_markdown, note_type, status, tags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                clean_ws(str(payload.get("title") or "Untitled note")),
                str(payload.get("body_markdown") or ""),
                self._valid_choice(payload.get("note_type", "idea"), NOTE_TYPES, "note type"),
                self._valid_choice(payload.get("status", "active"), NOTE_STATUSES, "note status"),
                dumps(sorted({str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()})),
                now,
                now,
            ),
        )
        return self.get_research_note(note_id)

    def list_research_notes(
        self,
        project_id: int | None = None,
        q: str = "",
        status: str = "",
        note_type: str = "",
        tag: str = "",
    ) -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        if note_type:
            clauses.append("note_type = ?")
            values.append(note_type)
        if q:
            clauses.append("(lower(title) LIKE ? OR lower(body_markdown) LIKE ?)")
            needle = f"%{q.lower()}%"
            values.extend([needle, needle])
        rows = self.store.query_all(
            f"SELECT * FROM research_notes {'WHERE ' + ' AND '.join(clauses) if clauses else ''} ORDER BY updated_at DESC, id DESC",
            tuple(values),
        )
        notes = [research_note_row(row) for row in rows]
        if tag:
            notes = [note for note in notes if tag in note["tags"]]
        for note in notes:
            note["links"] = self.research_note_links(note["id"])
        return notes

    def get_research_note(self, note_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_notes WHERE id = ?", (note_id,))
        if not row:
            raise KeyError("research note not found")
        note = research_note_row(row)
        note["links"] = self.research_note_links(note_id)
        return note

    def update_research_note(self, note_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_research_note(note_id)
        updates: list[str] = []
        values: list[Any] = []
        if "title" in payload:
            updates.append("title = ?")
            values.append(clean_ws(str(payload["title"])))
        if "body_markdown" in payload:
            updates.append("body_markdown = ?")
            values.append(str(payload["body_markdown"]))
        if "note_type" in payload:
            updates.append("note_type = ?")
            values.append(self._valid_choice(payload["note_type"], NOTE_TYPES, "note type"))
        if "status" in payload:
            updates.append("status = ?")
            values.append(self._valid_choice(payload["status"], NOTE_STATUSES, "note status"))
        if "tags" in payload:
            updates.append("tags_json = ?")
            values.append(dumps(sorted({str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()})))
        if updates:
            updates.append("updated_at = ?")
            values.append(utcnow())
            values.append(note_id)
            self.store.execute(f"UPDATE research_notes SET {', '.join(updates)} WHERE id = ?", tuple(values))
        return self.get_research_note(note_id)

    def create_research_link(self, note_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        note = self.get_research_note(note_id)
        link_type = self._valid_choice(payload.get("link_type"), LINK_TYPES, "link type")
        relation = self._valid_choice(payload.get("relation"), LINK_RELATIONS, "link relation")
        metadata = payload.get("metadata") or {}
        target_id = str(payload.get("target_id") or metadata.get("paper_id") or "")
        self._validate_research_link_target(link_type, target_id, metadata)
        now = utcnow()
        link_id = self.store.execute(
            """
            INSERT INTO research_links
                (project_id, note_id, discussion_message_id, link_type, relation, target_id,
                 target_uri, label, quote, metadata_json, created_at)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note["project_id"],
                note_id,
                link_type,
                relation,
                target_id,
                str(payload.get("target_uri") or ""),
                clean_ws(str(payload.get("label") or "")),
                str(payload.get("quote") or ""),
                dumps(metadata),
                now,
            ),
        )
        return self.get_research_link(link_id)

    def get_research_link(self, link_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_links WHERE id = ?", (link_id,))
        if not row:
            raise KeyError("research link not found")
        return research_link_row(row)

    def research_note_links(self, note_id: int) -> list[dict[str, Any]]:
        self.store.query_one("SELECT id FROM research_notes WHERE id = ?", (note_id,)) or self._raise_key_error(
            "research note not found"
        )
        return [
            research_link_row(row)
            for row in self.store.query_all(
                "SELECT * FROM research_links WHERE note_id = ? ORDER BY id",
                (note_id,),
            )
        ]

    def create_paper_research_note(self, paper_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        paper = self.get_paper(paper_id)
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        selected_text = clean_extracted_text(str(payload.get("selected_text") or ""))
        selected_image = payload.get("selected_image") or None
        if not selected_text and not selected_image:
            raise ValueError("selected_text or selected_image is required")
        body = selected_text or f"Selected region on page {payload.get('page_number') or selected_image.get('page')}"
        note = self.create_research_note(
            {
                "project_id": project_id,
                "title": payload.get("title") or f"Passage from {paper['title']}",
                "body_markdown": body,
                "note_type": "literature_note",
                "tags": payload.get("tags", []),
            }
        )
        metadata = {
            "paper_id": paper_id,
            "page_number": payload.get("page_number") or (selected_image or {}).get("page"),
            "selected_image": selected_image,
        }
        self.create_research_link(
            note["id"],
            {
                "link_type": "paper_region" if selected_image and not selected_text else "paper_passage",
                "relation": "supports",
                "target_id": str(paper_id),
                "label": paper["title"],
                "quote": selected_text,
                "metadata": metadata,
            },
        )
        return self.get_research_note(note["id"])

    def create_chat_message_research_note(self, message_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        message = self.store.query_one(
            """
            SELECT m.*, s.paper_id
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.id = ?
            """,
            (message_id,),
        )
        if not message:
            raise KeyError("chat message not found")
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        paper = self.get_paper(int(message["paper_id"]))
        note = self.create_research_note(
            {
                "project_id": project_id,
                "title": payload.get("title") or f"Answer from {paper['title']}",
                "body_markdown": message["content"],
                "note_type": "summary" if message["role"] == "assistant" else "question",
                "tags": payload.get("tags", []),
            }
        )
        self.create_research_link(
            note["id"],
            {
                "link_type": "chat_message",
                "relation": "cites",
                "target_id": str(message_id),
                "label": f"{paper['title']} chat message {message_id}",
                "quote": message["content"][:1200],
                "metadata": {"paper_id": paper["id"], "session_id": message["session_id"], "role": message["role"]},
            },
        )
        return self.get_research_note(note["id"])

    def create_experiment_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        status = self._valid_choice(payload.get("status", "planned"), EXPERIMENT_RUN_STATUSES, "experiment status")
        now = utcnow()
        run_id = self.store.execute(
            """
            INSERT INTO experiment_runs
                (project_id, title, status, hypothesis, dataset, code_ref, command,
                 parameters_json, metrics_json, summary, started_at, completed_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                clean_ws(str(payload.get("title") or "Untitled experiment run")),
                status,
                clean_ws(str(payload.get("hypothesis") or "")),
                clean_ws(str(payload.get("dataset") or "")),
                clean_ws(str(payload.get("code_ref") or "")),
                str(payload.get("command") or ""),
                dumps(payload.get("parameters") or {}),
                dumps(payload.get("metrics") or {}),
                str(payload.get("summary") or ""),
                clean_ws(str(payload.get("started_at") or "")),
                clean_ws(str(payload.get("completed_at") or "")),
                now,
                now,
            ),
        )
        return self.get_experiment_run(run_id)

    def list_experiment_runs(self, project_id: int | None = None, status: str = "") -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if status:
            clauses.append("status = ?")
            values.append(self._valid_choice(status, EXPERIMENT_RUN_STATUSES, "experiment status"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.store.query_all(
            f"SELECT * FROM experiment_runs {where} ORDER BY updated_at DESC, id DESC",
            tuple(values),
        )
        return [self._with_experiment_artifact_count(experiment_run_row(row)) for row in rows]

    def get_experiment_run(self, run_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM experiment_runs WHERE id = ?", (run_id,))
        if not row:
            raise KeyError("experiment run not found")
        return self._with_experiment_artifact_count(experiment_run_row(row))

    def _with_experiment_artifact_count(self, run: dict[str, Any]) -> dict[str, Any]:
        run["artifact_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM experiment_artifacts WHERE run_id = ?",
            (run["id"],),
        )["count"]
        return run

    def update_experiment_run(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_experiment_run(run_id)
        updates: list[str] = []
        values: list[Any] = []
        if "title" in payload:
            updates.append("title = ?")
            values.append(clean_ws(str(payload["title"])))
        if "status" in payload:
            updates.append("status = ?")
            values.append(self._valid_choice(payload["status"], EXPERIMENT_RUN_STATUSES, "experiment status"))
        if "hypothesis" in payload:
            updates.append("hypothesis = ?")
            values.append(clean_ws(str(payload["hypothesis"])))
        if "dataset" in payload:
            updates.append("dataset = ?")
            values.append(clean_ws(str(payload["dataset"])))
        if "code_ref" in payload:
            updates.append("code_ref = ?")
            values.append(clean_ws(str(payload["code_ref"])))
        if "command" in payload:
            updates.append("command = ?")
            values.append(str(payload["command"]))
        if "parameters" in payload:
            updates.append("parameters_json = ?")
            values.append(dumps(payload.get("parameters") or {}))
        if "metrics" in payload:
            updates.append("metrics_json = ?")
            values.append(dumps(payload.get("metrics") or {}))
        if "summary" in payload:
            updates.append("summary = ?")
            values.append(str(payload["summary"]))
        if "started_at" in payload:
            updates.append("started_at = ?")
            values.append(clean_ws(str(payload["started_at"] or "")))
        if "completed_at" in payload:
            updates.append("completed_at = ?")
            values.append(clean_ws(str(payload["completed_at"] or "")))
        if updates:
            updates.append("updated_at = ?")
            values.append(utcnow())
            values.append(run_id)
            self.store.execute(f"UPDATE experiment_runs SET {', '.join(updates)} WHERE id = ?", tuple(values))
        return self.get_experiment_run(run_id)

    def create_experiment_artifact(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self.get_experiment_run(run_id)
        artifact_type = self._valid_choice(
            payload.get("artifact_type", "other"),
            EXPERIMENT_ARTIFACT_TYPES,
            "experiment artifact type",
        )
        now = utcnow()
        artifact_id = self.store.execute(
            """
            INSERT INTO experiment_artifacts
                (run_id, artifact_type, uri, label, description, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact_type,
                str(payload.get("uri") or ""),
                clean_ws(str(payload.get("label") or artifact_type)),
                str(payload.get("description") or ""),
                dumps(payload.get("metadata") or {}),
                now,
            ),
        )
        return self.get_experiment_artifact(artifact_id)

    def experiment_run_artifacts(self, run_id: int) -> list[dict[str, Any]]:
        self.get_experiment_run(run_id)
        return [
            experiment_artifact_row(row)
            for row in self.store.query_all(
                "SELECT * FROM experiment_artifacts WHERE run_id = ? ORDER BY id",
                (run_id,),
            )
        ]

    def get_experiment_artifact(self, artifact_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM experiment_artifacts WHERE id = ?", (artifact_id,))
        if not row:
            raise KeyError("experiment artifact not found")
        return experiment_artifact_row(row)

    def create_experiment_research_note(self, run_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        run = self.get_experiment_run(run_id)
        project_id = int(payload.get("project_id") or run["project_id"])
        if project_id != run["project_id"]:
            raise ValueError("project_id must match experiment run project")
        body = "\n".join(
            [
                f"Experiment run: {run['title']}",
                f"Status: {run['status']}",
                f"Dataset: {run['dataset'] or '(none)'}",
                "",
                "Hypothesis:",
                run["hypothesis"] or "(none)",
                "",
                "Summary:",
                run["summary"] or "(none)",
            ]
        )
        note = self.create_research_note(
            {
                "project_id": project_id,
                "title": payload.get("title") or f"Experiment run: {run['title']}",
                "body_markdown": body,
                "note_type": "experiment_note",
                "tags": payload.get("tags", []),
            }
        )
        self.create_research_link(
            note["id"],
            {
                "link_type": "experiment_run",
                "relation": "supports",
                "target_id": str(run_id),
                "label": run["title"],
                "quote": run["summary"][:1200],
                "metadata": {"run_id": run_id, "status": run["status"], "metrics": run["metrics"]},
            },
        )
        return self.get_research_note(note["id"])

    def create_research_discussion(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = int(payload.get("project_id") or 0)
        self.get_research_project(project_id)
        status = self._valid_choice(payload.get("status", "active"), DISCUSSION_STATUSES, "discussion status")
        now = utcnow()
        discussion_id = self.store.execute(
            """
            INSERT INTO research_discussions (project_id, title, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                clean_ws(str(payload.get("title") or "Research discussion")),
                status,
                now,
                now,
            ),
        )
        return self.get_research_discussion(discussion_id)

    def list_research_discussions(
        self,
        project_id: int | None = None,
        status: str = "",
    ) -> list[dict[str, Any]]:
        clauses = []
        values: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            values.append(project_id)
        if status:
            clauses.append("status = ?")
            values.append(self._valid_choice(status, DISCUSSION_STATUSES, "discussion status"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.store.query_all(
            f"SELECT * FROM research_discussions {where} ORDER BY updated_at DESC, id DESC",
            tuple(values),
        )
        return [self._with_discussion_message_count(research_discussion_row(row)) for row in rows]

    def get_research_discussion(self, discussion_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_discussions WHERE id = ?", (discussion_id,))
        if not row:
            raise KeyError("research discussion not found")
        discussion = self._with_discussion_message_count(research_discussion_row(row))
        discussion["messages"] = self.research_discussion_messages(discussion_id)
        return discussion

    def _with_discussion_message_count(self, discussion: dict[str, Any]) -> dict[str, Any]:
        discussion["message_count"] = self.store.query_one(
            "SELECT COUNT(*) AS count FROM research_discussion_messages WHERE discussion_id = ?",
            (discussion["id"],),
        )["count"]
        return discussion

    def create_research_discussion_message(self, discussion_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        discussion = self.get_research_discussion(discussion_id)
        role = self._valid_choice(payload.get("role", "user"), DISCUSSION_MESSAGE_ROLES, "discussion message role")
        message_id = self.store.execute(
            """
            INSERT INTO research_discussion_messages
                (discussion_id, project_id, role, content, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                discussion_id,
                discussion["project_id"],
                role,
                str(payload.get("content") or ""),
                dumps(payload.get("metadata") or {}),
                utcnow(),
            ),
        )
        return self.get_research_discussion_message(message_id)

    def research_discussion_messages(self, discussion_id: int) -> list[dict[str, Any]]:
        self.store.query_one("SELECT id FROM research_discussions WHERE id = ?", (discussion_id,)) or self._raise_key_error(
            "research discussion not found"
        )
        return [
            research_discussion_message_row(row)
            for row in self.store.query_all(
                "SELECT * FROM research_discussion_messages WHERE discussion_id = ? ORDER BY id",
                (discussion_id,),
            )
        ]

    def get_research_discussion_message(self, message_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM research_discussion_messages WHERE id = ?", (message_id,))
        if not row:
            raise KeyError("research discussion message not found")
        return research_discussion_message_row(row)

    def create_discussion_research_link(self, message_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        message = self.get_research_discussion_message(message_id)
        link_type = self._valid_choice(payload.get("link_type"), LINK_TYPES, "link type")
        relation = self._valid_choice(payload.get("relation"), LINK_RELATIONS, "link relation")
        metadata = payload.get("metadata") or {}
        target_id = str(payload.get("target_id") or metadata.get("paper_id") or "")
        self._validate_research_link_target(link_type, target_id, metadata)
        link_id = self.store.execute(
            """
            INSERT INTO research_links
                (project_id, note_id, discussion_message_id, link_type, relation, target_id,
                 target_uri, label, quote, metadata_json, created_at)
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message["project_id"],
                message_id,
                link_type,
                relation,
                target_id,
                str(payload.get("target_uri") or ""),
                clean_ws(str(payload.get("label") or "")),
                str(payload.get("quote") or ""),
                dumps(metadata),
                utcnow(),
            ),
        )
        return self.get_research_link(link_id)

    def create_grounding_snapshot(self, project_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        project = self.get_research_project(project_id)
        discussion_message_id = payload.get("discussion_message_id")
        if discussion_message_id:
            message = self.get_research_discussion_message(int(discussion_message_id))
            if message["project_id"] != project_id:
                raise ValueError("discussion_message_id must belong to the project")
        content, metadata = self.build_grounding_snapshot_content(project_id)
        snapshot_id = self.store.execute(
            """
            INSERT INTO grounding_snapshots
                (project_id, discussion_message_id, title, content_markdown, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                int(discussion_message_id) if discussion_message_id else None,
                clean_ws(str(payload.get("title") or f"Grounding snapshot for {project['title']}")),
                content,
                dumps(metadata),
                utcnow(),
            ),
        )
        return self.get_grounding_snapshot(snapshot_id)

    def ask_research_discussion_codex(
        self,
        discussion_id: int,
        payload: dict[str, Any],
        codex_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        options = codex_options or {}
        discussion = self.get_research_discussion(discussion_id)
        project = self.get_research_project(discussion["project_id"])
        query = clean_ws(str(payload.get("content") or ""))
        if not query:
            raise ValueError("content is required")
        _prepare_codex_exec(options, "Codex research discussion is disabled. Set OPEN_ALPHAXIV_CODEX_ENABLED=true.")
        system_prompt = clean_ws(str(payload.get("system_prompt") or ""))[:4000]
        conversation_history = discussion["messages"][-12:]
        user_message = self.create_research_discussion_message(
            discussion_id,
            {
                "role": "user",
                "content": query,
                "metadata": {"source": "codex_research_discussion_turn"},
            },
        )
        snapshot = self.create_grounding_snapshot(
            project["id"],
            {
                "title": f"Codex grounding: {discussion['title']}",
                "discussion_message_id": user_message["id"],
            },
        )
        prompt = build_codex_research_discussion_prompt(
            project=project,
            query=query,
            grounding_snapshot=snapshot["content_markdown"],
            discussion_history=conversation_history,
            system_prompt=system_prompt,
        )
        answer, run_metadata = _run_codex_exec_prompt(
            prompt,
            options,
            "Codex research discussion is disabled. Set OPEN_ALPHAXIV_CODEX_ENABLED=true.",
            "Codex research discussion",
        )
        metadata = {
            "provider": "codex",
            "model": run_metadata.get("model") or "codex-local-agent",
            "answer_mode": "codex",
            "context_strategy": "research_grounding_snapshot",
            "user_message_id": user_message["id"],
            "grounding_snapshot_id": snapshot["id"],
            "grounding_snapshot_chars": len(snapshot["content_markdown"]),
            "system_prompt_preview": system_prompt[:240],
            "system_prompt_chars": len(system_prompt),
            "conversation_message_count": len(conversation_history),
            "project_id": project["id"],
            "discussion_id": discussion_id,
            **run_metadata,
        }
        assistant_message = self.create_research_discussion_message(
            discussion_id,
            {
                "role": "assistant",
                "content": answer,
                "metadata": metadata,
            },
        )
        return {
            "discussion_id": discussion_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "grounding_snapshot": snapshot,
            "answer": answer,
        }

    def build_grounding_snapshot_content(self, project_id: int) -> tuple[str, dict[str, Any]]:
        project = self.get_research_project(project_id)
        questions = self.list_research_questions(project_id=project_id)
        notes = self.list_research_notes(project_id=project_id)
        experiment_runs = self.list_experiment_runs(project_id=project_id)
        lines = [
            f"# Grounding Snapshot: {project['title']}",
            "",
            "## Project State",
            "",
            f"- Goal: {project['goal'] or '(none)'}",
            f"- Current state: {project['current_state'] or '(none)'}",
            "",
            "## Questions",
            "",
        ]
        if questions:
            for question in questions:
                lines.append(f"- [{question['status']}] {question['question']}")
        else:
            lines.append("(none)")
        lines.extend(["", "## Notes And Evidence", ""])
        if notes:
            for note in notes:
                lines.extend([f"### {note['title']}", "", note["body_markdown"] or "(empty)", ""])
                for link in note.get("links", []):
                    lines.append(f"- Evidence: {self.format_research_link_citation(link)}")
                lines.append("")
        else:
            lines.append("(none)")
        lines.extend(["", "## Experiment Runs", ""])
        if experiment_runs:
            for run in experiment_runs:
                lines.extend(
                    [
                        f"### {run['title']}",
                        "",
                        f"- Status: {run['status']}",
                        f"- Dataset: {run['dataset'] or '(none)'}",
                        f"- Summary: {run['summary'] or '(none)'}",
                    ]
                )
                if run["metrics"]:
                    for key, value in run["metrics"].items():
                        lines.append(f"- {key}: {value}")
                artifacts = self.experiment_run_artifacts(run["id"])
                for artifact in artifacts:
                    lines.append(f"- Artifact: {artifact['label'] or artifact['artifact_type']} ({artifact['uri']})")
                lines.append("")
        else:
            lines.append("(none)")
        metadata = {
            "question_count": len(questions),
            "note_count": len(notes),
            "experiment_run_count": len(experiment_runs),
        }
        return "\n".join(lines).strip() + "\n", metadata

    def list_grounding_snapshots(self, project_id: int) -> list[dict[str, Any]]:
        self.get_research_project(project_id)
        rows = self.store.query_all(
            "SELECT * FROM grounding_snapshots WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        )
        return [grounding_snapshot_row(row) for row in rows]

    def get_grounding_snapshot(self, snapshot_id: int) -> dict[str, Any]:
        row = self.store.query_one("SELECT * FROM grounding_snapshots WHERE id = ?", (snapshot_id,))
        if not row:
            raise KeyError("grounding snapshot not found")
        return grounding_snapshot_row(row)

    def research_dashboard(self) -> dict[str, Any]:
        counts = {
            "projects": self.store.query_one("SELECT COUNT(*) AS count FROM research_projects")["count"],
            "questions": self.store.query_one("SELECT COUNT(*) AS count FROM research_questions")["count"],
            "notes": self.store.query_one("SELECT COUNT(*) AS count FROM research_notes")["count"],
            "experiment_runs": self.store.query_one("SELECT COUNT(*) AS count FROM experiment_runs")["count"],
            "discussions": self.store.query_one("SELECT COUNT(*) AS count FROM research_discussions")["count"],
            "grounding_snapshots": self.store.query_one("SELECT COUNT(*) AS count FROM grounding_snapshots")["count"],
        }
        rows = self.store.query_all(
            """
            SELECT
                p.*,
                (SELECT COUNT(*) FROM research_questions q WHERE q.project_id = p.id) AS question_count,
                (SELECT COUNT(*) FROM research_notes n WHERE n.project_id = p.id) AS note_count,
                (SELECT COUNT(*) FROM experiment_runs r WHERE r.project_id = p.id) AS experiment_run_count,
                (SELECT COUNT(*) FROM research_discussions d WHERE d.project_id = p.id) AS discussion_count,
                (SELECT COUNT(*) FROM grounding_snapshots s WHERE s.project_id = p.id) AS grounding_snapshot_count
            FROM research_projects p
            WHERE p.status = 'active'
            ORDER BY p.updated_at DESC, p.id DESC
            LIMIT 10
            """
        )
        return {"counts": counts, "active_projects": [dict(row) for row in rows]}

    def search_research(
        self,
        q: str,
        project_id: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = clean_ws(q)
        if not query:
            return []
        if project_id:
            self.get_research_project(project_id)
        needle = f"%{query.lower()}%"
        limit = max(1, min(int(limit or 50), 100))
        project_clause = "AND project_id = ?" if project_id else ""
        project_values: tuple[Any, ...] = (project_id,) if project_id else ()
        results: list[dict[str, Any]] = []

        project_rows = self.store.query_all(
            """
            SELECT id, id AS project_id, title, goal, current_state, created_at
            FROM research_projects
            WHERE (lower(title) LIKE ? OR lower(goal) LIKE ? OR lower(current_state) LIKE ?)
            """
            + (" AND id = ?" if project_id else "")
            + " ORDER BY updated_at DESC, id DESC LIMIT ?",
            (needle, needle, needle, *project_values, limit),
        )
        for row in project_rows:
            results.append(
                research_search_result(
                    "research_project",
                    row,
                    row["title"],
                    search_snippet(row["goal"], row["current_state"], row["title"], query=query),
                    row["created_at"],
                )
            )

        query_specs = [
            (
                "research_question",
                """
                SELECT id, project_id, question AS title, question, current_answer, created_at
                FROM research_questions
                WHERE (lower(question) LIKE ? OR lower(current_answer) LIKE ?)
                """,
                ("question", "current_answer"),
            ),
            (
                "research_note",
                """
                SELECT id, project_id, title, body_markdown, created_at
                FROM research_notes
                WHERE (lower(title) LIKE ? OR lower(body_markdown) LIKE ?)
                """,
                ("title", "body_markdown"),
            ),
            (
                "experiment_run",
                """
                SELECT id, project_id, title, hypothesis, dataset, code_ref, command, metrics_json, summary, created_at
                FROM experiment_runs
                WHERE (
                    lower(title) LIKE ? OR lower(hypothesis) LIKE ? OR lower(dataset) LIKE ?
                    OR lower(code_ref) LIKE ? OR lower(command) LIKE ? OR lower(metrics_json) LIKE ?
                    OR lower(summary) LIKE ?
                )
                """,
                ("title", "hypothesis", "dataset", "code_ref", "command", "metrics_json", "summary"),
            ),
            (
                "research_discussion",
                """
                SELECT id, project_id, title, title AS body, created_at
                FROM research_discussions
                WHERE lower(title) LIKE ?
                """,
                ("title", "body"),
            ),
            (
                "research_discussion_message",
                """
                SELECT id, project_id, role AS title, content, created_at
                FROM research_discussion_messages
                WHERE lower(content) LIKE ?
                """,
                ("title", "content"),
            ),
            (
                "grounding_snapshot",
                """
                SELECT id, project_id, title, content_markdown, created_at
                FROM grounding_snapshots
                WHERE (lower(title) LIKE ? OR lower(content_markdown) LIKE ?)
                """,
                ("title", "content_markdown"),
            ),
        ]
        for result_type, base_sql, fields in query_specs:
            if len(results) >= limit:
                break
            placeholders = base_sql.count("?")
            values: list[Any] = [needle] * placeholders
            sql = base_sql
            if project_id:
                sql += f" {project_clause}"
                values.extend(project_values)
            sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
            values.append(limit - len(results))
            for row in self.store.query_all(sql, tuple(values)):
                title = row["title"] or result_type.replace("_", " ").title()
                snippet = search_snippet(*(row.get(field) for field in fields), query=query)
                results.append(research_search_result(result_type, row, title, snippet, row["created_at"]))
                if len(results) >= limit:
                    break
        return results

    def export_research_project(self, project_id: int) -> str:
        project = self.get_research_project(project_id)
        questions = self.list_research_questions(project_id=project_id)
        experiment_runs = self.list_experiment_runs(project_id=project_id)
        discussions = self.list_research_discussions(project_id=project_id)
        snapshots = self.list_grounding_snapshots(project_id)
        notes = self.list_research_notes(project_id=project_id)
        lines = [
            f"# {project['title']}",
            "",
            f"- Status: {project['status']}",
            f"- Slug: {project['slug']}",
            "",
            "## Goal",
            "",
            project["goal"] or "(none)",
            "",
            "## Current State",
            "",
            project["current_state"] or "(none)",
            "",
            "## Questions",
            "",
        ]
        if questions:
            for question in questions:
                answer = f" - {question['current_answer']}" if question["current_answer"] else ""
                lines.append(f"- [{question['status']}] {question['question']}{answer}")
        else:
            lines.append("(none)")
        lines.extend(["", "## Experiment Runs", ""])
        if not experiment_runs:
            lines.append("(none)")
        for run in experiment_runs:
            lines.extend(
                [
                    f"### {run['title']}",
                    "",
                    f"- Status: {run['status']}",
                    f"- Dataset: {run['dataset'] or '(none)'}",
                    f"- Code: {run['code_ref'] or '(none)'}",
                    "",
                    "Hypothesis:",
                    "",
                    run["hypothesis"] or "(none)",
                    "",
                    "Command:",
                    "",
                    f"```bash\n{run['command']}\n```" if run["command"] else "(none)",
                    "",
                    "Metrics:",
                ]
            )
            if run["metrics"]:
                for key, value in run["metrics"].items():
                    lines.append(f"- {key}: {value}")
            else:
                lines.append("(none)")
            lines.extend(["", "Summary:", "", run["summary"] or "(none)", ""])
            artifacts = self.experiment_run_artifacts(run["id"])
            if artifacts:
                lines.append("Artifacts:")
                for artifact in artifacts:
                    label = artifact["label"] or artifact["artifact_type"]
                    lines.append(f"- {label}: {artifact['uri']}")
                lines.append("")
        lines.extend(["", "## Discussions", ""])
        if not discussions:
            lines.append("(none)")
        for discussion in discussions:
            lines.extend([f"### {discussion['title']}", "", f"- Status: {discussion['status']}", ""])
            full_discussion = self.get_research_discussion(discussion["id"])
            for message in full_discussion.get("messages", []):
                lines.extend([f"**{message['role']}**", "", message["content"] or "(empty)", ""])
        lines.extend(["", "## Grounding Snapshots", ""])
        if not snapshots:
            lines.append("(none)")
        for snapshot in snapshots:
            lines.extend([f"### {snapshot['title']}", "", snapshot["content_markdown"], ""])
        lines.extend(["", "## Notes", ""])
        if not notes:
            lines.append("(none)")
        for note in notes:
            lines.extend([f"### {note['title']}", "", note["body_markdown"] or "(empty)", ""])
            if note.get("links"):
                lines.append("Evidence:")
                for link in note["links"]:
                    citation = self.format_research_link_citation(link)
                    if link.get("quote"):
                        lines.append(f"- {citation}: {link['quote']}")
                    else:
                        lines.append(f"- {citation}")
                lines.append("")
        return "\n".join(lines).strip() + "\n"

    def format_research_link_citation(self, link: dict[str, Any]) -> str:
        metadata = link.get("metadata") or {}
        if link["link_type"] in {"paper", "paper_passage", "paper_region"}:
            paper_id = int(metadata.get("paper_id") or link.get("target_id") or 0)
            paper = self.get_paper(paper_id)
            page = metadata.get("page_number")
            page_label = f", p.{page}" if page else ""
            return f"[{paper['title']}{page_label}]"
        if link["link_type"] == "chat_message":
            return f"[Chat message {link['target_id']}]"
        if link["link_type"] == "experiment_run":
            run = self.get_experiment_run(int(link.get("target_id") or 0))
            return f"[Experiment run: {run['title']}]"
        if link["link_type"] == "experiment_artifact":
            artifact = self.get_experiment_artifact(int(link.get("target_id") or 0))
            label = artifact["label"] or artifact["artifact_type"]
            return f"[Experiment artifact: {label}]"
        return f"[{link['label'] or link['target_uri'] or link['target_id']}]"

    def _valid_choice(self, value: Any, allowed: set[str], label: str) -> str:
        clean = clean_ws(str(value or ""))
        if clean not in allowed:
            raise ValueError(f"invalid {label}: {clean}")
        return clean

    def _unique_project_slug(self, value: str, current_project_id: int | None = None) -> str:
        base = slugify(value)
        slug = base
        suffix = 2
        while True:
            row = self.store.query_one("SELECT id FROM research_projects WHERE slug = ?", (slug,))
            if not row or row["id"] == current_project_id:
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1

    def _validate_research_link_target(self, link_type: str, target_id: str, metadata: dict[str, Any]) -> None:
        if link_type in {"paper", "paper_passage", "paper_region"}:
            paper_id = int(metadata.get("paper_id") or target_id or 0)
            self.get_paper(paper_id)
        if link_type == "chat_message":
            row = self.store.query_one("SELECT id FROM chat_messages WHERE id = ?", (int(target_id or 0),))
            if not row:
                raise KeyError("chat message not found")
        if link_type == "experiment_run":
            self.get_experiment_run(int(target_id or 0))
        if link_type == "experiment_artifact":
            self.get_experiment_artifact(int(target_id or 0))

    def _raise_key_error(self, message: str) -> None:
        raise KeyError(message)


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
    paper_context: str,
    selected_text: str,
    selected_image: dict[str, Any] | None,
    system_prompt: str,
    conversation_history: list[dict[str, Any]],
    file_references: dict[str, str],
    options: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    prompt = build_codex_paper_prompt(
        paper,
        query,
        paper_context,
        selected_text,
        selected_image,
        system_prompt,
        conversation_history,
        file_references,
    )
    answer, exec_metadata = _run_codex_exec_prompt(
        prompt,
        options,
        "Codex paper chat is disabled. Set OPEN_ALPHAXIV_CODEX_ENABLED=true.",
        "Codex paper chat",
    )
    return answer, {
        **exec_metadata,
        "context_strategy": "full_text",
        "context_scope": "selection" if selected_text or selected_image else "whole_paper",
        "paper_context_chars": len(paper_context),
        "system_prompt_chars": len(system_prompt),
        "conversation_message_count": len(conversation_history),
        "paper_file_references": file_references,
    }


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
        stderr = clean_ws(result.stderr)[-500:]
        raise RuntimeError(f"{failure_label} failed: {stderr or 'codex exec exited with an error'}")
    answer = result.stdout.strip()
    if not answer:
        raise RuntimeError(f"{failure_label} returned an empty answer.")
    return answer, {
        "codex_sandbox": prepared["sandbox"],
        "codex_cli_path": prepared["resolved_cli"],
        "codex_stderr_preview": clean_ws(result.stderr)[-500:],
        "model": prepared["model"] or "codex-local-agent",
    }


def build_codex_paper_prompt(
    paper: dict[str, Any],
    query: str,
    paper_context: str,
    selected_text: str,
    selected_image: dict[str, Any] | None,
    system_prompt: str = "",
    conversation_history: list[dict[str, Any]] | None = None,
    file_references: dict[str, str] | None = None,
) -> str:
    context_limit = 75_000
    clean_context = clean_extracted_text(paper_context)
    if clean_context:
        truncated = len(clean_context) > context_limit
        context = clean_context[:context_limit]
        if truncated:
            context = context.rsplit(" ", 1)[0] + "\n\n[Paper context was truncated to fit the local Codex prompt budget.]"
    else:
        context = "(No extracted paper text is available.)"
    selected = clean_ws(selected_text)[:1800] or "(none)"
    custom_instructions = clean_ws(system_prompt)[:4000] or "(none)"
    image = format_selected_image(selected_image)
    history = format_conversation_history(conversation_history or [])
    links = format_paper_file_references(file_references or {})
    context_scope = (
        "The user selected a specific passage or image region. Treat that selection as the primary focus."
        if selected_text or selected_image
        else "No passage or image region is selected. Treat the whole paper file and extracted paper context as the active context."
    )
    return textwrap.dedent(
        f"""
        You are answering a research paper question inside Open AlphaXiv Local.

        Constraints:
        - Use only the paper metadata, selected passage, selected image region metadata, and paper context below.
        - Do not edit files, run shell commands, browse the web, or ask for more context.
        - If the evidence is insufficient, say exactly what is missing.
        - Prefer concise answers grounded in the paper context over retrieval-style chunk citations.
        - Keep the answer concise and technical.
        - Preserve continuity with the conversation history when it is relevant.

        Context scope:
        {context_scope}

        User-configured system prompt:
        {custom_instructions}

        Paper:
        Title: {paper['title']}
        arXiv: {paper.get('arxiv_id') or paper.get('source_id')}
        Authors: {', '.join(paper.get('authors', []))}

        Paper file references:
        {links}

        Conversation history:
        {history}

        Selected passage:
        {selected}

        Selected image region:
        {image}

        Question:
        {query}

        Paper context:
        {context}
        """
    ).strip()


def build_codex_research_discussion_prompt(
    project: dict[str, Any],
    query: str,
    grounding_snapshot: str,
    discussion_history: list[dict[str, Any]] | None = None,
    system_prompt: str = "",
) -> str:
    context_limit = 75_000
    clean_snapshot = clean_extracted_text(grounding_snapshot)
    if clean_snapshot:
        truncated = len(clean_snapshot) > context_limit
        context = clean_snapshot[:context_limit]
        if truncated:
            context = (
                context.rsplit(" ", 1)[0]
                + "\n\n[Research grounding context was truncated to fit the local Codex prompt budget.]"
            )
    else:
        context = "(No research grounding snapshot is available.)"
    history = format_conversation_history(discussion_history or [])
    custom_instructions = clean_ws(system_prompt)[:4000] or "(none)"
    return textwrap.dedent(
        f"""
        You are a project-level research assistant inside Open AlphaXiv Local.

        Constraints:
        - Use only the project state, discussion history, user question, and grounding snapshot below.
        - Do not edit files, run shell commands, browse the web, or ask for more context.
        - If the evidence is insufficient, say exactly what project data, experiment data, paper evidence, or code evidence is missing.
        - Preserve continuity with the discussion history when it is relevant.
        - Answer in Markdown.

        User-configured system prompt:
        {custom_instructions}

        Project:
        Title: {project.get('title') or '(untitled)'}
        Goal: {project.get('goal') or '(none)'}
        Current state: {project.get('current_state') or '(none)'}

        Discussion history:
        {history}

        Question:
        {query}

        Grounding snapshot:
        {context}
        """
    ).strip()


def format_conversation_history(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "(none)"
    lines = []
    for message in messages[-12:]:
        role = str(message.get("role", "message"))
        content = clean_ws(str(message.get("content", "")))[:1200]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(none)"


def format_paper_file_references(file_references: dict[str, str]) -> str:
    rows = [
        ("Landing URL", file_references.get("landing_url", "")),
        ("PDF URL", file_references.get("pdf_url", "")),
        ("Local PDF path", file_references.get("local_pdf_path", "")),
    ]
    lines = [f"- {label}: {value}" for label, value in rows if value]
    return "\n".join(lines) if lines else "(none)"


def format_selected_image(selected_image: dict[str, Any] | None) -> str:
    if not selected_image:
        return "(none)"
    page = selected_image.get("page")
    x = selected_image.get("x")
    y = selected_image.get("y")
    width = selected_image.get("width")
    height = selected_image.get("height")
    return (
        f"page={page}, x={x}%, y={y}%, width={width}%, height={height}%."
        " This identifies a visual region selected by the reader; no image pixels are attached in this prompt."
    )


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


def research_project_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def research_question_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def research_note_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "tags": loads(row.get("tags_json"), []),
    }


def research_link_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "metadata": loads(row.get("metadata_json"), {}),
    }


def experiment_run_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "parameters": loads(row.get("parameters_json"), {}),
        "metrics": loads(row.get("metrics_json"), {}),
    }


def experiment_artifact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "metadata": loads(row.get("metadata_json"), {}),
    }


def research_discussion_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def research_discussion_message_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "metadata": loads(row.get("metadata_json"), {}),
    }


def grounding_snapshot_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "metadata": loads(row.get("metadata_json"), {}),
    }
