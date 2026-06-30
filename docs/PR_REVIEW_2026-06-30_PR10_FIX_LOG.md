# PR Review 2026-06-30 PR10 Fix Log

- PR: https://github.com/solitude6060/open-alphaxiv/pull/10
- Fix commit: `69251736ffec33207078e5e8caad345d298e8007`

## Triage Table

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Codex run failure could persist a partial turn. | Claude | MEDIUM | `Store.execute` commits per write; original flow wrote user message and snapshot before `_run_codex_exec_prompt`. | Fixed. Added regression test and moved persistence after successful Codex execution. |
| Ask Codex button allowed repeated clicks during a long request. | Claude | LOW | Button disabled condition did not include an in-flight state. | Fixed. Added `researchCodexBusy`. |
| Duplicate selected-discussion GET. | Claude, OpenCode | LOW/MEDIUM | `refreshResearch` and the `selectedDiscussionId` effect could fetch the same id. | Fixed. Shared `loadResearchDiscussion`; effect handles id changes, refresh handles same-id reloads. |
| Unbounded Codex discussion content. | OpenCode | MEDIUM | `ResearchDiscussionCodexAsk.content` had no Pydantic limit. | Fixed. Added `max_length=5000`; capped `system_prompt` at 4000. |
| Unbounded project fields in prompt. | Claude | LOW | `project.goal` and `project.current_state` were interpolated without caps. | Fixed. Added title, goal, and current-state caps. |
| Redundant metadata `model` assignment. | Claude | LOW | Explicit `model` was overwritten by `**run_metadata`. | Fixed. Removed the redundant explicit field. |
| RuntimeError maps to HTTP 400. | Claude, OpenCode | LOW / non-blocking | Existing paper chat endpoint uses the same convention. | Deferred. Should be handled across paper and research Codex endpoints together. |

## Regression Tests Added

- `tests/test_services.py::test_research_discussion_codex_failure_does_not_persist_partial_turn`

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest` -> 60 passed.
- `npm run build` -> passed.
- `git diff --check` -> clean.
