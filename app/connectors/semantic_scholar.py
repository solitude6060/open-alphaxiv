from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

import httpx


S2_HOST = "api.semanticscholar.org"
S2_ATTRIBUTION = "Data from Semantic Scholar"


def validate_s2_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or parsed.hostname != S2_HOST:
        raise ValueError("Semantic Scholar requests may only use https://api.semanticscholar.org")
    return str(url).strip()


def _author_names(paper: dict[str, Any]) -> list[str]:
    names = []
    for author in paper.get("authors") or []:
        if isinstance(author, dict) and author.get("name"):
            names.append(str(author["name"]))
        elif isinstance(author, str) and author.strip():
            names.append(author.strip())
    return names


def _node(paper: dict[str, Any], group: str) -> dict[str, Any]:
    paper_id = str(paper.get("paperId") or "")
    year_raw = paper.get("year") or 0
    try:
        year = int(year_raw)
    except (TypeError, ValueError):
        year = 0
    external_ids = paper.get("externalIds") or {}
    arxiv_id = ""
    if isinstance(external_ids, dict):
        arxiv_id = str(external_ids.get("ArXiv") or "")
    url = str(paper.get("url") or "")
    if arxiv_id:
        url = url or f"https://arxiv.org/abs/{arxiv_id}"
    return {
        "external_id": paper_id,
        "arxiv_id": arxiv_id,
        "title": str(paper.get("title") or "Untitled paper"),
        "year": year,
        "group": group,
        "citation_count": int(paper.get("citationCount") or 0),
        "url": url,
        "authors": _author_names(paper),
        "abstract": str(paper.get("abstract") or ""),
        "venue": str(paper.get("venue") or ""),
    }


def build_graph_from_s2(
    seed: dict[str, Any],
    references: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen: set[str] = set()
    seed_id = str(seed.get("paperId") or "")
    if not seed_id:
        raise ValueError("Semantic Scholar seed is missing paperId")
    seed_node = _node(seed, "seed")
    nodes.append(seed_node)
    seen.add(seed_id)
    for row in references or []:
        paper = row.get("citedPaper") if isinstance(row, dict) else None
        if not isinstance(paper, dict) or not paper.get("paperId"):
            continue
        paper_id = str(paper["paperId"])
        if paper_id not in seen:
            nodes.append(_node(paper, "prior"))
            seen.add(paper_id)
        edges.append(
            {
                "source": seed_id,
                "target": paper_id,
                "edge_type": "cites",
                "score": 1.0,
                "explanation": "Seed paper cites this work.",
            }
        )
    for row in citations or []:
        paper = row.get("citingPaper") if isinstance(row, dict) else None
        if not isinstance(paper, dict) or not paper.get("paperId"):
            continue
        paper_id = str(paper["paperId"])
        if paper_id not in seen:
            nodes.append(_node(paper, "derivative"))
            seen.add(paper_id)
        edges.append(
            {
                "source": paper_id,
                "target": seed_id,
                "edge_type": "cited_by",
                "score": 1.0,
                "explanation": "This work cites the seed paper.",
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "attribution": S2_ATTRIBUTION,
        "status": "ok",
        "status_reason": "",
    }


def _headers(api_key: str = "") -> dict[str, str]:
    headers = {"User-Agent": "open-alphaxiv/0.1 (local research workspace)"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def request_s2_json(
    url: str,
    api_key: str = "",
    timeout_s: float = 20.0,
    sleeper: Callable[[float], None] | None = None,
    retries: int = 1,
) -> dict[str, Any]:
    import time

    validate_s2_url(url)
    wait = sleeper or time.sleep
    last_error: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        with httpx.Client(timeout=timeout_s, follow_redirects=False) as client:
            response = client.get(url, headers=_headers(api_key))
        if response.status_code == 429 and attempt < retries:
            retry_after = response.headers.get("Retry-After") or "2"
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 2.0
            wait(min(max(delay, 0.0), 30.0))
            continue
        if response.status_code == 429:
            raise RuntimeError(
                "Semantic Scholar rate-limited this request (HTTP 429). "
                "Set SEMANTIC_SCHOLAR_API_KEY and retry."
            )
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            last_error = exc
            raise
        if not isinstance(payload, dict):
            raise RuntimeError("Semantic Scholar returned a non-object JSON payload.")
        return payload
    raise RuntimeError(str(last_error) if last_error else "Semantic Scholar request failed.")


FIELDS = "paperId,title,year,abstract,citationCount,externalIds,url,authors,venue"


def fetch_paper_neighborhood(arxiv_id: str, api_key: str = "", limit: int = 50) -> dict[str, Any]:
    from urllib.parse import quote

    ident = quote(f"ARXIV:{arxiv_id}", safe=":")
    cap = max(1, min(int(limit or 50), 50))
    paper = request_s2_json(
        f"https://{S2_HOST}/graph/v1/paper/{ident}?fields={FIELDS}",
        api_key=api_key,
    )
    references = request_s2_json(
        f"https://{S2_HOST}/graph/v1/paper/{ident}/references?fields={FIELDS}&limit={cap}",
        api_key=api_key,
    )
    citations = request_s2_json(
        f"https://{S2_HOST}/graph/v1/paper/{ident}/citations?fields={FIELDS}&limit={cap}",
        api_key=api_key,
    )
    return build_graph_from_s2(paper, references.get("data") or [], citations.get("data") or [])
