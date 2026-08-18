# AlphaXiv-Workflow Recreation Plan

> **For agentic workers:** ADR-0002 and ADR-0003 are accepted. Phase 1 and
> Phase 2 code are in the tree. Implement the next unchecked phase only
> after reading `docs/CANONICAL.md`. Evidence:
> `docs/PHASE1_EVIDENCE.md`, `docs/PHASE2_EVIDENCE.md`.

**Goal:** A local researcher can run the daily alphaXiv reading loop on this
machine, answering paper questions with their own coding-agent subscriptions
and APIs, without calling alphaxiv.org or redistributing arXiv PDFs.

**Architecture:** Local FastAPI + Vite app owns papers and notes. Agents
connect through MCP. In-app Ask Paper spawns official CLIs or calls
OpenAI-compatible HTTP. Literature metadata comes from Semantic Scholar.
Discovery comes from the arXiv API.

**Tech stack (frozen until a migration PR):** Python 3 FastAPI, SQLite,
Vite/React, Docker Compose, Poppler, official `codex` / `claude` /
`opencode` binaries on the host.

**Spec:** `docs/PRODUCT_CONTRACT.md`, `docs/LEGAL_BOUNDARY.md`,
`docs/AGENT_ARCHITECTURE.md`.

## Global constraints

- No alphaxiv.org HTTP. No unofficial alphaxiv client libraries.
- No public PDF hosting. Every paper row has `landing_url`.
- arXiv API: ≤ 1 request / 3 seconds. PDF fetches: honor robots crawl-delay.
- Secrets stay server-side. MCP binds to localhost in v1.
- Claude Pro/Max: official `claude` binary or Console API key only.
- Tests first for each adapter and each ingest/graph change.
- English in repo docs and commits. No `Co-Authored-By` AI trailers.

## Done already (do not rebuild)

- arXiv URL ingest, local PDF upload, page images, text layer, mock chat
- Codex `exec` paper chat and research-discussion Codex
- Research projects, notes, links, experiments, discussions, dashboard search
- Bookmarks, tags, markdown export
- Docker Compose boot of web + api (worker is a stub)

## Phase map

```text
Phase 0  Contract freeze          docs only
Phase 1  Agent runtime            MCP + CLI adapters + live HTTP
Phase 2  Discovery + true graph   feed, search, Semantic Scholar
Phase 3  Reader parity            pdf.js or full-page render, folders, citations
Phase 4  Hardening                auth-optional LAN, rate limits, split god files
Phase 5  Optional extras          GitHub links, Zotero, multi-user
```

Each phase is independently usable. Stop after Phase 1 if the agent path
fails on this machine; that failure changes the product, not the legal
boundary.

---

## Phase 0: Contract freeze

**Deliverables**

- [x] `docs/LEGAL_BOUNDARY.md`
- [x] `docs/AGENT_ARCHITECTURE.md`
- [x] `docs/PRODUCT_CONTRACT.md`
- [x] `docs/ADR-0002-legal-local-recreation.md`
- [x] `docs/ADR-0003-agent-subscription-architecture.md`
- [x] User written acceptance of ADRs (operator merge request 2026-08-18)
- [x] `LICENSE` (MIT or Apache-2.0) and `NOTICE` (arXiv + S2 attribution)
- [x] README paragraph: local-only, original product, link to legal boundary

**Exit criteria**

- User written "accept" on ADR-0002 and ADR-0003.
- LICENSE present. README does not describe the app as an official alphaXiv
  product.

**Evidence required:** those files on `main`.

---

## Phase 1: Agent runtime

**Why first:** the user's load-bearing new requirement is subscription + API
use. Discovery UI without a legal agent path would repeat the 2026-06
over-spec.

**Files (target split)**

- Create: `app/agents/protocol.py`
- Create: `app/agents/codex.py` (move from `app/services.py`)
- Create: `app/agents/claude_cli.py`
- Create: `app/agents/opencode.py`
- Create: `app/agents/openai_compatible.py`
- Create: `app/agents/registry.py`
- Create: `app/mcp/server.py`
- Create: `app/mcp/tools.py`
- Modify: `app/main.py` — `/api/agents/status`, `/mcp`
- Modify: `web/src/main.tsx` — agent picker (split later if the file must
  grow more than ~200 lines)
- Test: `tests/test_agents.py`, `tests/test_mcp.py`, HTTP tests in
  `tests/test_api.py`

**Interfaces**

```python
class AgentRunResult(TypedDict):
    ok: bool
    text: str
    adapter: str
    binary_path: str
    latency_ms: int
    exit_code: int
    stderr_preview: str
    model: str

class AgentAdapter(Protocol):
    name: str
    def probe(self) -> dict[str, Any]: ...
    def run(self, prompt: str, *, timeout_s: int) -> AgentRunResult: ...
```

HTTP:

- `GET /api/agents/status` → `{codex, claude_cli, opencode, openai_compatible}`
  each with `available: bool` and `reason: str`
- `POST /api/chat/messages` gains `answer_mode` values:
  `mock | codex | claude_cli | opencode | openai_compatible`
- MCP Streamable HTTP at `/mcp` (localhost)

**Exit criteria**

| Criterion | Evidence |
| --- | --- |
| Codex path still green | existing pytest Codex cases pass |
| Claude CLI adapter | unit test with fake binary; live probe documented as manual |
| OpenCode adapter | same |
| OpenAI-compatible chat | integration test against `httpx` mock; healthcheck hits `/v1/models` or a tiny chat |
| MCP `list_library` / `get_paper_text` / `search_arxiv` | pytest with in-memory store |
| UI shows which adapters are available | screenshot or Playwright later; for Phase 1, status JSON is enough |
| Cursor can be configured | README snippet for `.cursor/mcp.json` pointing at `http://127.0.0.1:8000/mcp` |

**Phase 1b (after Phase 1 green, not a blocker):** streamed in-app Codex
through official `codex app-server`, which OpenAI documents for embedding
Codex in another product (`https://developers.openai.com/codex/app-server`).
This is the OpenClaw-class path. Keep `codex exec` as the fallback.

**Manual evidence on the operator machine (2026-08-18):**

1. `codex exec` on an ingested fixture: ran; host usage limit until
   2026-08-20 13:52.
2. `claude -p` (no `--bare`) answered the same fixture question after the
   stdin adapter fix.
3. Cursor Agent UI listing was not driven. HTTP `tools/list` returned
   seven tools. README has `.cursor/mcp.json`.
4. OpenAI-compatible mode: pytest against `httpx` fakes. No live key or
   Ollama run.

Phase 2 started after an explicit skip of waiting for every Phase 1 live
row. Claude and OpenCode later went green. Codex and Cursor Agent UI
remain operator checks, not a reason to reopen Phase 1 code.

Detailed steps: `docs/plans/2026-08-17-phase1-agent-runtime.md`.

---

## Phase 2: Discovery and true literature graph

**User-visible loop:** library home shows a feed; search finds arXiv papers;
opening a result ingests; Similar panel is real papers.

**Files**

- Create: `app/connectors/arxiv.py` — query, id_list, category list, rate
  limiter
- Create: `app/connectors/semantic_scholar.py` — paper, citations,
  references; cache by paper id
- Modify: `app/services.py` `build_literature_graph` — delete synthetic
  `mvp1-local` generator
- Create: `app/services/feed.py` — watched categories, last-seen ids
- Modify: `web` — Feed tab, search results as cards, graph node detail with
  S2 attribution
- Test: rate limiter unit tests; graph scoring tests with fixture JSON
  captured from S2 docs examples (no live network in CI)

**Feed algorithm (v1)**

1. Operator configures one or more arXiv categories (example: `cs.LG`).
2. Poll `http://export.arxiv.org/api/query?search_query=cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=25`
   on a manual refresh and at most once per 15 minutes automatically.
3. Store metadata only until the user opens a paper (PDF fetch is on demand).
4. Cards show title, authors, submitted date, abstract, arXiv id, landing
   URL.

**Graph algorithm (replace SPEC literature graph with a bounded v1)**

1. Resolve seed to Semantic Scholar paper id via arXiv id.
2. Fetch references and citations (capped, e.g. 50 each).
3. Score: direct cite > bibliographic coupling Jaccard > co-citation Jaccard
   > abstract cosine when embeddings exist.
4. Classify prior / derivative / related by year and edge direction.
5. Persist nodes/edges. Show attribution: "Data from Semantic Scholar".

**Exit criteria**

- Feed shows ≥ 10 real papers for `cs.LG` on a networked machine.
- Graph for `1706.03762` contains real titles, not `Prior work 1: ...`.
- CI uses recorded fixtures; a documented manual command hits live S2.
- Failed S2 calls surface `status_reason`, no fake fill.

Status 2026-08-18: code and CI fixtures are in the working tree
(`docs/plans/2026-08-17-phase2-discovery-graph.md`,
`docs/PHASE2_EVIDENCE.md`). Live `cs.LG` feed returned 25 real rows.
Live S2 neighborhood for `1706.03762` returned HTTP 429 without
`SEMANTIC_SCHOLAR_API_KEY` and stored no fake nodes. Bibliographic
coupling / co-citation Jaccard scoring is deferred; v1 classifies
prior/derivative from cite direction only.

---

## Phase 3: Reader and library parity

**Reader**

- Render all pages. Poppler `max_pages` default is 80 as of 2026-08-18.
  Prefer browser `pdf.js` against the locally stored PDF bytes so Poppler
  page images become a fallback.
- Persist highlights and region selections as notes (already partially
  present via research links).
- Page-level citations in Ask Paper for HTTP and MCP answers. Codex mode
  may keep full-text prompting (ADR-0001) but must still store a passage
  quote when the user selected text.

**Library**

- Folders: Want to read / Reading / Completed / custom, matching the
  MCP library tools in `docs/AGENT_ARCHITECTURE.md`.
- Tags and bookmarks remain.
- Similar papers panel uses Phase 2 graph.

**Summaries**

- Replace `summarize()` template in `app/services.py:2442` with an adapter
  call when a generation provider is healthy; keep the template as mock.

**Exit criteria**

- A 40-page PDF is readable to the last page.
- Highlight → note round-trip survives reload.
- Folder MCP tools pass pytest.
- Answer metadata includes chunk or page ids for HTTP mode.

---

## Phase 4: Hardening

- Split `app/services.py` by domain (ingest, chat, research, graph) without
  behavior change. Workflow E / mechanical extract.
- Split `web/src/main.tsx` into `library`, `reader`, `research`, `settings`.
- Worker becomes a real queue when ingest is slow: start with a thread pool
  inside the API; only then Redis.
- [x] Drop unused Postgres/Redis from default Compose
  (`docker-compose.yml` has api, web, worker only).
- Optional localhost password or single-user session for LAN.
- Structured logs at ingest, adapter probe, MCP tool call, generation.
- `Dockerfile.web` production image uses `npm run build` + `vite preview`
  or nginx, not `npm run dev`.
- License field on papers; UI links to arXiv for downloads.

**Exit criteria**

- `docker compose up --build` serves a production web build.
- Compose has no unused healthy-but-idle databases, or Postgres is the
  real store (pick one in a sub-ADR).
- ruff/mypy/pytest green; web `tsc --noEmit` green.

---

## Phase 5: Optional extras (after daily loop works)

- Papers with Code / GitHub repo links on the paper page
- Zotero import (little-alphaxiv already has this; evaluate MIT reuse)
- Multi-paper compare
- Browser extension that only rewrites `arxiv.org/abs` → local app (no
  alphaxiv.org URL hijack)
- Audio: out unless a user-supplied TTS API is configured
- Copilot SDK: only after GitHub OAuth is real
- Cursor `agent -p` / `@cursor/sdk`: only if MCP is not enough for in-app
  turns; use `CURSOR_API_KEY` or `agent login`

---

## Explicitly never in this track

- Public comments network
- Researcher directory
- Conference/event hubs
- Pro billing
- Claiming arXiv or alphaXiv endorsement
- Training a model on cached PDFs for redistribution

## Research notebook

Projects, experiments, discussions, grounding snapshots stay as a module
behind a Research tab. They must not block Phases 1–3. No new notebook
tables until Phase 3 is green, unless a bug fix is required.

## Risk register

| Risk | Mitigation |
| --- | --- |
| Anthropic tightens `claude -p` | MCP-first still works; in-app Claude adapter becomes API-key only |
| arXiv blocks PDF fetches | On-demand fetch, crawl-delay, user upload fallback |
| S2 rate limits | Cache, backoff, fixture tests |
| `services.py` merge conflicts | Split in Phase 4; Phase 1 adds packages beside it |
| Trademark complaint on repo name | Rename before public marketing; LEGAL_BOUNDARY already requires it |

## Staffing for execution

1. Phase 1 and Phase 2 are implemented. Next code is Phase 3, or a live
   Semantic Scholar graph retry after `SEMANTIC_SCHOLAR_API_KEY` is set.
2. Later phases get their own plan file before coding.
3. Triple-review on agent and connector PRs (credentials, subprocess, SSRF
   on PDF URLs).

## First-principles recap

- Need: daily reading loop + spend existing agent seats.
- Assumption discarded: clone alphaxiv.org including social graph and wrap
  Cursor internally.
- Verified: MCP is how alphaXiv, Claude Code, Codex, and Cursor integrate.
- If MCP were wrong, the fallback is CLI spawn + API keys, which Phase 1
  also ships.
- Current activity: Phase 3 reader work after the live graph row is green
  or explicitly skipped.
