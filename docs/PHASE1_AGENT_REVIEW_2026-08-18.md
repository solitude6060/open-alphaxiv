# Phase 1 agent-runtime review

Date: 2026-08-18
Reviewers: two independent Cursor code-reviewer passes on 2026-08-18.
The first pass read MCP `search_arxiv` before it reused the arXiv
connector. The second pass re-read after that reuse.
Base: `f86240be1c34d480a88f6fa1ac673c6d0130b2a2`
Scope: uncommitted Phase 1 agent runtime (`app/agents/`, `app/mcp/`, related
Ask Paper wiring).

## Findings

| ID | Severity | Location | Issue | This change? |
| --- | --- | --- | --- | --- |
| P1-1 | Important | `app/main.py` `POST /mcp` | Async route called `handle_mcp_request` on the event loop. `search_arxiv` can `time.sleep` up to 3s; `ingest_paper` downloads and extracts a PDF. That freezes the API and UI. Both reviewers reported this. | Yes |
| P1-2 | Important | `app/mcp/tools.py` `search_arxiv` | First reviewer: MCP search called `app.services.fetch_text` with no 3-second interval. Second reviewer: already gone after MCP reused `app.connectors.arxiv.search_arxiv`. | Yes |

No Critical findings.

Checked and holding: no `alphaxiv.org` client; Claude spawn is `claude -p`
without `--bare`; adapters live under `app/agents/`; OpenAI-compatible SSRF
rejects `file://` and link-local HTTP; `/api/agents/status` keys match the
plan.

Residual notes (not blocking this change): Docker/uvicorn still bind
`0.0.0.0:8000`, so `/mcp` is reachable on the LAN unless the process is
bound to loopback. Live Cursor MCP listing was not run.
`test_openai_compatible_answer_mode_requires_healthy_provider` only covers a
missing provider, not `health_status=failed`.

## Verdict

P1-1 and P1-2 are required before treating MCP as a safe arXiv client on the
same API process as the web UI. Fixes: `docs/PHASE1_AGENT_REVIEW_2026-08-18_FIX_LOG.md`.
