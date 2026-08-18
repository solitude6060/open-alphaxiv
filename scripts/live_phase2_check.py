#!/usr/bin/env python3
"""Live Phase 2 check against export.arxiv.org and api.semanticscholar.org.

Does not download PDFs. Writes a compact JSON summary to stdout.
Uses a gitignored sqlite file under data/live-verify/.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import PaperService
from app.store import Store, dumps, utcnow


def _insert_arxiv_seed(service: PaperService, arxiv_id: str) -> int:
    now = utcnow()
    existing = service.store.query_one(
        "SELECT id FROM papers WHERE source_type = 'arxiv' AND source_id = ?",
        (arxiv_id,),
    )
    if existing:
        return int(existing["id"])
    return service.store.execute(
        """
        INSERT INTO papers
            (source_type, source_id, arxiv_id, title, abstract, authors_json,
             published_at, pdf_url, landing_url, status, summary, created_at, updated_at)
        VALUES ('arxiv', ?, ?, ?, ?, ?, ?, ?, ?, 'ready', ?, ?, ?)
        """,
        (
            arxiv_id,
            arxiv_id,
            f"Live seed {arxiv_id}",
            "Metadata-only seed for a live Semantic Scholar neighborhood check.",
            dumps(["Live verify"]),
            "",
            f"https://arxiv.org/pdf/{arxiv_id}",
            f"https://arxiv.org/abs/{arxiv_id}",
            "Live Semantic Scholar graph check.",
            now,
            now,
        ),
    )


def main() -> int:
    dest = (ROOT / "data" / "live-verify").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    service = PaperService(Store(dest / "live.db"), dest)
    feed = service.refresh_feed("cs.LG", force=True)
    paper_id = _insert_arxiv_seed(service, "1706.03762")
    graph = service.build_literature_graph(paper_id)
    titles = [node["title"] for node in graph.get("nodes") or []]
    landing = [item["landing_url"] for item in feed.get("items") or []]
    pdfs = list(dest.rglob("*.pdf"))
    summary = {
        "feed_category": feed.get("category"),
        "feed_item_count": len(feed.get("items") or []),
        "feed_skipped": feed.get("skipped"),
        "feed_sample_titles": [item["title"] for item in (feed.get("items") or [])[:5]],
        "feed_landing_hosts": sorted({url.split("/")[2] for url in landing if "://" in url}),
        "pdf_files_on_disk": [str(path) for path in pdfs],
        "graph_status": graph.get("status"),
        "graph_status_reason": graph.get("status_reason"),
        "graph_attribution": graph.get("attribution"),
        "graph_node_count": len(graph.get("nodes") or []),
        "graph_edge_count": len(graph.get("edges") or []),
        "graph_sample_titles": titles[:8],
        "has_prior_work_placeholder": any(title.startswith("Prior work") for title in titles),
        "semantic_scholar_api_key_present": bool(os.environ.get("SEMANTIC_SCHOLAR_API_KEY")),
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    ok_feed = int(summary["feed_item_count"] or 0) >= 10 and "arxiv.org" in summary["feed_landing_hosts"]
    ok_graph = (
        summary["graph_status"] == "ok"
        and summary["graph_node_count"] >= 3
        and summary["graph_attribution"] == "Data from Semantic Scholar"
        and not summary["has_prior_work_placeholder"]
        and any("Attention" in title for title in titles)
    )
    ok_no_pdf = summary["pdf_files_on_disk"] == []
    if ok_feed and ok_graph and ok_no_pdf:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
