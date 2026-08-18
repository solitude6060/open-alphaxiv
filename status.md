# Status

Snapshot date: 2026-08-18

## Product

Local-first paper workspace. Living contract: `docs/CANONICAL.md`.
`docs/SPEC.md` / `docs/PRD.md` / `docs/MVP_ROADMAP.md` are historical.

## Evidence

- Pytest: 98 passed (`env PYTHONPATH=.:.deps python3 -m pytest -q --tb=line`).
- Web: `cd web && npm run build` succeeded (Vite 8.1.0).
- Compose file: `docker compose config -q` exit 0. Images not built.
- Live arXiv feed: 25 `cs.LG` rows, landing host `arxiv.org`, no PDF files.
  `scripts/live_phase2_check.py`.
- Live Semantic Scholar graph for `1706.03762`: HTTP 429 without
  `SEMANTIC_SCHOLAR_API_KEY`. Empty graph, no `Prior work N` fill.
  See `docs/PHASE2_EVIDENCE.md`.
- Live paper Q&A: Claude and OpenCode answered a local fixture; Codex hit
  a usage limit until 2026-08-20 13:52. `docs/PHASE1_EVIDENCE.md`.
  `scripts/live_phase1_qa.py`.

## Decisions in force

- ADR-0002 accepted: legally bounded local recreation.
- ADR-0003 accepted: MCP-first + official CLI spawn + OpenAI-compatible HTTP.
- `open-` does not immunize a public `alphaxiv` product name.
- Operator asked to commit, merge, and push this branch to `main`.

## Next gate

Set `SEMANTIC_SCHOLAR_API_KEY` and re-run `scripts/live_phase2_check.py` to
close the live graph row. Public rename remains a user decision. Cursor
Agent UI listing and a live Codex answer after the usage-limit reset remain
operator checks. Phase 3 is the next code track.
