from __future__ import annotations

import re
from threading import Lock
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse

import httpx


ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")
CATEGORY_RE = re.compile(r"^[a-z][a-z-]+(\.[A-Za-z][A-Za-z0-9-]+)?$")
ARXIV_HOST = "export.arxiv.org"


class IntervalLimiter:
    def __init__(
        self,
        min_interval_s: float = 3.0,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        import time

        self.min_interval_s = float(min_interval_s)
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._last: float | None = None
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            if self.min_interval_s <= 0:
                self._last = now
                return
            if self._last is None:
                self._last = now
                return
            gap = self.min_interval_s - (now - self._last)
            if gap > 0:
                self._sleeper(gap)
                now = self._clock()
            self._last = now


ARXIV_LIMITER = IntervalLimiter(min_interval_s=3.0)


def validate_arxiv_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != ARXIV_HOST:
        raise ValueError("arxiv requests may only use https://export.arxiv.org")
    return url


def fetch_text(url: str, timeout: float = 8.0) -> str:
    validate_arxiv_url(url)
    ARXIV_LIMITER.wait()
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.get(
            url,
            headers={"User-Agent": "open-alphaxiv/0.1 (local research workspace)"},
        )
        response.raise_for_status()
        return response.text


def _xml_text(xml: str, tag: str) -> str:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1).replace("&amp;", "&")).strip()


def parse_atom_entries(feed: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for entry in re.findall(r"<entry>(.*?)</entry>", feed or "", re.S):
        arxiv_match = ARXIV_ID_RE.search(entry)
        if not arxiv_match:
            continue
        arxiv_id = arxiv_match.group(1)
        authors = [_xml_text(block, "name") for block in re.findall(r"<author>(.*?)</author>", entry, re.S)]
        authors = [name for name in authors if name]
        results.append(
            {
                "arxiv_id": arxiv_id,
                "title": _xml_text(entry, "title") or f"arXiv paper {arxiv_id}",
                "abstract": _xml_text(entry, "summary"),
                "authors": authors,
                "published_at": _xml_text(entry, "published"),
                "landing_url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
            }
        )
    return results


def search_arxiv(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise ValueError("query is required")
    limit = max(1, min(int(max_results or 10), 25))
    url = (
        f"https://{ARXIV_HOST}/api/query"
        f"?search_query=all:{quote_plus(cleaned)}&start=0&max_results={limit}"
    )
    return parse_atom_entries(fetch_text(url))


def list_category(category: str, max_results: int = 25) -> list[dict[str, Any]]:
    cleaned = str(category or "").strip()
    if not CATEGORY_RE.match(cleaned):
        raise ValueError("category must look like cs.LG")
    limit = max(1, min(int(max_results or 25), 25))
    url = (
        f"https://{ARXIV_HOST}/api/query"
        f"?search_query=cat:{quote_plus(cleaned)}"
        f"&sortBy=submittedDate&sortOrder=descending&start=0&max_results={limit}"
    )
    return parse_atom_entries(fetch_text(url))


def fetch_by_id(arxiv_id: str) -> dict[str, Any] | None:
    match = ARXIV_ID_RE.search(str(arxiv_id or ""))
    if not match:
        raise ValueError("Expected an arXiv identifier such as 2201.08239")
    url = f"https://{ARXIV_HOST}/api/query?id_list={match.group(1)}"
    rows = parse_atom_entries(fetch_text(url))
    return rows[0] if rows else None
