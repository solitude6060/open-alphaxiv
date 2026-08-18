# Product Contract

Effective: 2026-08-17 (accepted)

This file is the product contract. Historical `docs/PRD.md`, `docs/SPEC.md`,
and `docs/MVP_ROADMAP.md` are not constraints. Index: `docs/CANONICAL.md`.

## One-sentence product

A local-first paper workspace: discover arXiv work, read the PDF, ask
grounded questions through the user's own coding agents or APIs, keep notes,
and inspect related literature — without hosting a public clone of alphaXiv.

## Users

The operator of a single machine or a trusted LAN. Not anonymous internet
tenants.

## Success for "complete recreation"

A researcher can replace their daily alphaXiv **reading loop** on this
machine:

1. See new papers in watched arXiv categories.
2. Search by query and open a paper.
3. Read the PDF with selectable text.
4. Ask questions against the paper.
5. Save notes and highlights.
6. See related / prior / derivative papers from Semantic Scholar.
7. Continue the same work from Claude Code, Codex, or Cursor through MCP.

Success is not: public comments, researcher social graph, events, Pro
billing, audio, or a hosted copy of alphaxiv.org.

## Non-goals (frozen)

- Public multi-tenant hosting of arXiv PDFs.
- Calling alphaxiv.org or api.alphaxiv.org.
- Browser extension, audio summaries, conference hubs.
- Replacing Connected Papers' corpus-scale ranking.
- Using Claude Pro/Max OAuth inside a custom HTTP client or the Claude
  Agent SDK.

## Stack that is actually in the tree

Keep it until a dedicated migration PR:

- Web: Vite + React + TypeScript (`web/package.json`, `web/src/main.tsx`)
- API: FastAPI (`app/main.py`)
- Store: SQLite (`app/store.py`)
- Jobs: synchronous in the API process (`app/worker.py` currently sleeps)
- Docker Compose: web, api, worker; SQLite volume only

Do not introduce Next.js, pgvector, or a second job queue until a later
phase names the scale trigger (concurrent ingest > 1 and library > 2k
papers).

## Domain that stays

Papers, artifacts, chunks, chat sessions, bookmarks, tags, research
projects, notes, evidence links, experiment runs, discussions, grounding
snapshots. These already have HTTP routes in `app/main.py`.

## Domain that is added

- Folders (reading status + custom collections)
- Paper license + landing URL enforcement
- Agent adapter registry
- MCP session
- Real literature nodes from Semantic Scholar
- arXiv category watchers / local feed
- Real embeddings from the configured embedding provider

## UX layout

Reader-first: PDF (or page images + text layer) on the left; assistant,
notes, and similar-papers on the right. Discovery is a separate library
home with a feed and search box.

## Quality bar

- Every model answer stores adapter, model, prompt version, and source
  identifiers.
- Secrets never reach the frontend bundle.
- arXiv clients honor the 3-second API interval and robots crawl-delay
  for `/pdf`.
- Tests: unit for adapters and arXiv id normalization; integration for
  ingest and MCP tool dispatch with fakes; one Docker smoke for health +
  mock chat.

## Naming

Private working title: Open AlphaXiv Local. The git folder may keep that
string while the app is localhost-only.

Public title: choose before any public GitHub marketing. The prefix `open-`
does not make `alphaxiv` safe as a competing mark
(`docs/PRODUCT_EVALUATION_2026-08-17.md`). Candidate descriptive names (not
a brand exercise): Paperlocal, Local Papers, Arxwork. The user picks; the
code can keep the current module path until rename.
