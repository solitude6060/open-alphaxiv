# Phase 2 Discovery and Literature Graph Implementation Plan

**Status:** implemented 2026-08-18. Evidence: `docs/PHASE2_EVIDENCE.md`.
Live Semantic Scholar graph still needs `SEMANTIC_SCHOLAR_API_KEY`.
Do not restore the synthetic `mvp1-local` generator.

> **For agentic workers:** This plan is an archive of the Phase 2 task
> split. Remaining checkboxes are historical process, not open work.

**Goal:** Library feed shows real arXiv category results; Similar panel shows
real Semantic Scholar papers, not generated `Prior work N` titles.

**Architecture:** New `app/connectors/` talks only to `export.arxiv.org` and
`api.semanticscholar.org`. `PaperService.build_literature_graph` deletes the
synthetic generator and persists S2 nodes/edges. Feed stores metadata until
the user ingests. CI uses fixtures; no live network in pytest.

**Tech Stack:** FastAPI, sqlite, httpx, pytest, existing Vite UI.

**Spec:** `docs/PRODUCT_CONTRACT.md`, `docs/ALPHAXIV_RECREATION_PLAN.md`
Phase 2, `docs/LEGAL_BOUNDARY.md`.

## Global Constraints

- No alphaxiv.org requests.
- arXiv: one request every three seconds; HTTPS `export.arxiv.org` only.
- Semantic Scholar: HTTPS `api.semanticscholar.org` only; attribution string
  `Data from Semantic Scholar` on graph payloads.
- Failed S2 calls set `status_reason`; never invent nodes.
- Do not download PDFs for feed cards.
- Skip git commits unless the user asks.

---

### Task 1: arXiv connector + interval limiter

**Files:**
- Create: `app/connectors/__init__.py`
- Create: `app/connectors/arxiv.py`
- Modify: `app/mcp/tools.py` to call the connector
- Test: `tests/test_connectors.py`

- [x] **Step 1:** Failing tests for `wait_for_arxiv_slot` sleeping when
  called twice inside 3 seconds (inject fake clock/sleeper), category query
  URL host `export.arxiv.org`, and rejected non-arxiv hosts.
- [x] **Step 2:** Run pytest, confirm import/fail for the right reason.
- [x] **Step 3:** Minimal limiter + `search_arxiv` / `list_category` using
  `fetch_text` from `app.services` or a local httpx GET with host check.
- [x] **Step 4:** pytest pass. Point MCP `search_arxiv` at the connector.

---

### Task 2: Semantic Scholar client + graph scoring

**Files:**
- Create: `app/connectors/semantic_scholar.py`
- Create: `tests/fixtures/s2_attention.json`
- Test: `tests/test_connectors.py`

- [x] **Step 1:** Failing tests: allowlist host; reject `http://169.254.169.254`;
  `build_graph_from_s2(seed, references, citations)` classifies prior /
  derivative from cite direction; titles come from fixture, not `Prior work`.
- [x] **Step 2:** Run to fail.
- [x] **Step 3:** Implement GET `/graph/v1/paper/ARXIV:{id}` plus
  `/references` and `/citations` with optional `SEMANTIC_SCHOLAR_API_KEY`.
- [x] **Step 4:** pytest pass.

Cite-direction scoring shipped. Bibliographic coupling / co-citation Jaccard
from the recreation plan remains deferred; v1 does not invent those scores.

---

### Task 3: Replace synthetic literature graph

**Files:**
- Modify: `app/services.py`, `app/store.py` (`literature_builds`)
- Modify: `tests/test_services.py` ingest assertion
- Modify: `web/src/main.tsx` attribution + empty/failure reason

- [x] **Step 1:** Failing test: ingest does not create `mvp1-local` nodes;
  `literature_graph` without a build returns empty + `status_reason`;
  build with monkeypatched S2 fixture stores real titles and attribution.
- [x] **Step 2:** Run to fail.
- [x] **Step 3:** Delete synthetic generator. GET does not auto-fill.
- [x] **Step 4:** pytest + existing graph consumers still return the same
  JSON shape plus `status`, `status_reason`, `attribution`.

---

### Task 4: Category feed

**Files:**
- Modify: `app/store.py` feed tables
- Modify: `app/services.py` or `app/services_feed.py` if extract is cheaper
  as methods on `PaperService`
- Modify: `app/main.py` `GET/POST /api/feed`
- Modify: `web/src/main.tsx` feed list + ingest-from-card
- Modify: `.env.example` `OPEN_ALPHAXIV_ARXIV_CATEGORIES=cs.LG`
- Test: `tests/test_api.py`

- [x] **Step 1:** Failing API test: refresh with fake arXiv XML stores ≥1
  item with landing URL on arxiv.org and no PDF bytes on disk; second
  refresh inside 15 minutes without `force` does not call the network.
- [x] **Step 2:** Run to fail.
- [x] **Step 3:** Implement. Default category `cs.LG`.
- [x] **Step 4:** pytest pass.

---

### Task 5: Remaining mechanical product gaps (same track)

These do not need a user decision:

- MCP `list_notes` and `query_paper_pages` from `docs/AGENT_ARCHITECTURE.md`
- Raise Poppler `max_pages` default from 12 to 80
- `Dockerfile.web` production `npm run build` + `vite preview`
- Remove unused Compose postgres/redis `depends_on` so API starts on SQLite
  alone (living Phase 4: do not keep idle databases)

- [x] Tests then minimal implementation for each.

---

### Task 6: Review + docs

- [x] Land findings from the Phase 1 reviewer that are P0/P1.
- [x] Update `status.md`, `tracker.md`, `handover.md`, `docs/PHASE2_EVIDENCE.md`
  with real commands only.

## Self-review

- Feed and graph are independently usable.
- Legal: arXiv metadata only on feed; S2 attribution; no fake fill.
- Ingest test that required 20 synthetic nodes is rewritten, not weakened
  into asserting nothing.
