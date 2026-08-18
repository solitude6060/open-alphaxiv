# Phase 2 discovery-graph review

Date: 2026-08-18
Reviewer: Cursor code-reviewer pass on the uncommitted Phase 2 tree
Scope: `app/connectors/`, literature graph, feed, MCP tools, Compose/Docker web

## Findings

| ID | Severity | Location | Issue | This change? |
| --- | --- | --- | --- | --- |
| P2-1 | Important | `app/services.py` `literature_graph`; leftover `literature_nodes` | `CREATE TABLE IF NOT EXISTS` leaves `mvp1-local` rows. GET with nodes and no `literature_builds` row returns them as `status=ok` with attribution `Data from Semantic Scholar`. A failed S2 build also leaves those rows. | Yes |

No Critical findings.

Green-field constraints that hold: no `alphaxiv.org` client; arXiv HTTPS
`export.arxiv.org` with a 3-second limiter; S2 HTTPS
`api.semanticscholar.org`; feed stores metadata only; GET does not
auto-build on a fresh database.

## Verdict

P2-1 must be fixed before an existing `./data` or Compose volume can show
the Similar panel. Fresh ingest already returns an empty graph.
