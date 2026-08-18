# Handover

Updated: 2026-08-18

## This session

Operator asked to converge project documents, then commit, merge, and
push.

Document convergence:

- `docs/CANONICAL.md` now indexes living files, records, historical
  archives, and the 2026-08-18 implementation status.
- Phase 1 and Phase 2 plan files are marked implemented.
- `docs/ALPHAXIV_RECREATION_PLAN.md` no longer says Phase 1 live rows are
  still open as a code blocker.
- `README.md` has the host run path for Claude / OpenCode.
- `docs/SPEC.md` no longer claims the running app follows the 2026-06
  contract.

## Findings to keep

- Unauthenticated Semantic Scholar from this host is currently 429.
- Host Codex cannot answer until 2026-08-20 13:52 unless the operator
  buys credits.
- Cursor Agent UI listing cannot be driven from this process. HTTP
  `tools/list` is the engineering equivalent.
- Graph v1 uses direct cite / cited-by only.

## Next session

1. Re-run `scripts/live_phase2_check.py` after setting
   `SEMANTIC_SCHOLAR_API_KEY`.
2. Phase 3 after the live graph row is green or explicitly skipped.
3. Retry Codex paper Q&A after the usage-limit reset.

## Commands

```bash
env PYTHONPATH=.:.deps python3 -m pytest
env PYTHONPATH=.:.deps python3 scripts/live_phase2_check.py
env PYTHONPATH=.:.deps OPEN_ALPHAXIV_CODEX_ENABLED=true OPEN_ALPHAXIV_CLAUDE_ENABLED=true OPEN_ALPHAXIV_OPENCODE_ENABLED=true python3 scripts/live_phase1_qa.py
cd web && npm run build
```
