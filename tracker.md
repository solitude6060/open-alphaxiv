# Tracker

Updated: 2026-08-18

## Current track

`docs/ALPHAXIV_RECREATION_PLAN.md`

| ID | Item | Status |
| --- | --- | --- |
| P0 | Contract freeze; old SPEC/PRD/roadmap superseded | Done |
| P1 | Agent runtime: adapters + MCP | Done in tree; Claude/OpenCode live fixture Q&A green; Codex usage-limited until 2026-08-20 13:52 |
| P2 | arXiv feed + Semantic Scholar graph | Done in tree; live feed green; live S2 429 without API key |
| P3 | Reader parity (pdf.js, folders, citations) | Next code track; Poppler default is 80 pages |
| P4 | Hardening (split god files) | Partial: Compose idle databases removed; `services.py` still large |
| P5 | Optional Zotero / GitHub / extension | Deferred |

## Near-term

1. Operator: put `SEMANTIC_SCHOLAR_API_KEY` in `.env` and re-run
   `scripts/live_phase2_check.py`.
2. Phase 3 after the live graph row is green or explicitly skipped.
3. Parked: Cursor Agent UI listing, public rename, Codex retry after
   2026-08-20 13:52.

## Parked

- Bibliographic coupling / co-citation Jaccard graph scoring.
- Research notebook feature growth (projects/experiments already shipped).
- Public multi-tenant hosting.
- Using api.alphaxiv.org.
