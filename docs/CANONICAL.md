# Canonical documents

Effective: 2026-08-17. Snapshot: 2026-08-18.

Older files in this repository describe a 2026-06 MVP1 that mixed
unimplemented infrastructure (Next.js, PostgreSQL, pgvector, Redis workers,
Markitdown) with features that later landed as a SQLite + Vite notebook.
Those files are **historical**. They must not steer new work.

If a living document and a historical document disagree, the living
document wins. Do not spend implementation time reconciling them.

## Living (implement against these)

| File | Role |
| --- | --- |
| `docs/PRODUCT_CONTRACT.md` | Product contract |
| `docs/LEGAL_BOUNDARY.md` | Legal envelope |
| `docs/AGENT_ARCHITECTURE.md` | Agent/MCP/CLI/HTTP runtimes |
| `docs/PRODUCT_EVALUATION_2026-08-17.md` | Naming, Codex/OpenClaw, good-product tests |
| `docs/ALPHAXIV_RECREATION_PLAN.md` | Phase map |
| `docs/plans/2026-08-17-phase1-agent-runtime.md` | Phase 1 agent runtime plan (implemented) |
| `docs/plans/2026-08-17-phase2-discovery-graph.md` | Phase 2 feed and literature graph plan (implemented) |
| `docs/ADR-0001-codex-full-paper-context.md` | Still in force for Codex paper prompts |
| `docs/ADR-0002-legal-local-recreation.md` | Accepted |
| `docs/ADR-0003-agent-subscription-architecture.md` | Accepted |

Stack that exists in the tree (Vite, FastAPI, SQLite, in-process ingest) is
the stack. Do not add Postgres, Redis, Next.js, or a job queue because a
superseded spec listed them. Add them only when a living phase names a
scale trigger.

Operator session files `status.md`, `tracker.md`, and `handover.md` are
local only. They are gitignored and must not be committed.

## Records (evidence and reviews; not a spec)

| File | Role |
| --- | --- |
| `docs/PHASE1_EVIDENCE.md` | Host probes and live paper Q&A |
| `docs/PHASE2_EVIDENCE.md` | Live feed and Semantic Scholar graph |
| `docs/PHASE1_AGENT_REVIEW_2026-08-18.md` | Phase 1 review |
| `docs/PHASE1_AGENT_REVIEW_2026-08-18_FIX_LOG.md` | Phase 1 remediations |
| `docs/PHASE2_GRAPH_REVIEW_2026-08-18.md` | Phase 2 review |
| `docs/PHASE2_GRAPH_REVIEW_2026-08-18_FIX_LOG.md` | Phase 2 remediations |
| `docs/REVIEW_2026-08-17.md` | Pre-implementation review |
| `docs/SURVEY_2026-08-17.md` | 2026-08 survey |

## Historical (do not implement from)

| File | Why it is kept |
| --- | --- |
| `docs/SPEC.md` | 2026-06 intended contract; drifted from code |
| `docs/PRD.md` | 2026-06 product requirements |
| `docs/MVP_ROADMAP.md` | 2026-06 phase list |
| `docs/research-survey.md` | 2026-06-28 survey; replaced by `docs/SURVEY_2026-08-17.md` |
| `docs/plans/2026-06-30-*.md` | Completed MVP1 feature plans |
| `docs/PR_REVIEW_*.md` | Review archives |

## Implementation status (2026-08-18)

- Phase 0 documents, `LICENSE`, and `NOTICE` are in the tree.
- Phase 1 adapters and localhost MCP are in the tree. Live fixture Q&A:
  Claude and OpenCode answered; Codex hit a usage limit until
  2026-08-20 13:52. Cursor Agent UI listing was not driven; HTTP
  `tools/list` returns seven tools.
- Phase 2 feed and Semantic Scholar graph are in the tree. Live `cs.LG`
  feed returned 25 rows. Live graph for `1706.03762` returned HTTP 429
  without `SEMANTIC_SCHOLAR_API_KEY` and stored no fake nodes.
- Phase 3 (pdf.js, folders, citations) is not started. Poppler default is
  80 pages.
- Phase 4 file splits are not started. Compose no longer starts unused
  Postgres or Redis. `Dockerfile.web` uses `npm run build` plus
  `vite preview`.
