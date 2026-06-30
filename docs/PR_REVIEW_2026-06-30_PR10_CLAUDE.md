# PR Review 2026-06-30 PR10 Claude

- PR: https://github.com/solitude6060/open-alphaxiv/pull/10
- Base branch: `main`
- Head branch: `feature/research-discussion-codex`
- Reviewed head SHA: `11b04eaeb38e4555e2002049606448a74dcb470b`
- Reviewer command: `claude -p "$(cat /tmp/pr10_review_prompt.txt)"`
- Raw output: `/tmp/pr10_review_claude.out`

## Verdict

APPROVE with one MEDIUM follow-up recommended.

## Findings

| Finding | Severity | Reviewer Evidence | Triage | Fix Status |
|---|---:|---|---|---|
| Codex run failure could leave a user message and grounding snapshot before the assistant answer is stored. | MEDIUM | `app/services.py` persisted user message and snapshot before `_run_codex_exec_prompt`. `Store.execute` commits per call. | Accepted. This could inflate snapshots and leave ambiguous discussion history on operational Codex failure. | Fixed in `6925173`: Codex now runs before persistence, and `tests/test_services.py::test_research_discussion_codex_failure_does_not_persist_partial_turn` covers the failure path. |
| RuntimeError maps to HTTP 400 instead of 5xx. | LOW | `app/main.py` maps `(ValueError, RuntimeError)` to 400. | Deferred. Existing paper chat uses the same convention, so changing both belongs in a separate compatibility pass. | Not changed. |
| Ask Codex button was not disabled while a request was in flight. | LOW | `web/src/main.tsx` cleared input only after success, leaving double-click possible. | Accepted. Long Codex calls make repeated clicks plausible. | Fixed in `6925173` with `researchCodexBusy`. |
| Duplicate selected-discussion GET. | LOW | `refreshResearch` fetched selected discussion and the `selectedDiscussionId` effect fetched it again. | Accepted. Not correctness-critical, but easy to remove. | Fixed in `6925173` by using the effect on id changes and an explicit refresh only when the id is unchanged. |
| Project fields were not capped in the research prompt. | LOW | Snapshot and history had caps, but `goal` and `current_state` did not. | Accepted. | Fixed in `6925173` with title, goal, and current-state caps in `build_codex_research_discussion_prompt`. |
| Redundant metadata `model` assignment. | LOW | Explicit `model` was overwritten by `**run_metadata`. | Accepted. | Fixed in `6925173` by relying on `run_metadata`. |

## Verification After Fix

- `env PYTHONPATH=.:.deps python3 -m pytest` -> 60 passed.
- `npm run build` -> passed.
- `git diff --check` -> clean.
