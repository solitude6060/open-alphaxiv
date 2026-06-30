# PR Review 2026-06-30 PR10 AGY

- PR: https://github.com/solitude6060/open-alphaxiv/pull/10
- Base commit before PR10: `30694ca`
- Merge commit reviewed: `e4bfb4c5b185f3727bb7354370c02f9f2dfc58a9`
- Final PR head before merge: `26ff91eb297e567dc87746b3f24a59a4fe91d7bb`
- Reviewer command: `agy --print-timeout 15m --dangerously-skip-permissions -p "$(cat /tmp/pr10_review_prompt_agy_final.txt)"`
- Raw output: `/tmp/pr10_review_agy_final.out`

## Verdict

APPROVE.

## Findings

| Finding | Severity | Reviewer Evidence | Triage | Fix Status |
|---|---:|---|---|---|
| RuntimeError and ValueError from Codex execution map to HTTP 400 instead of more specific 5xx/504 status codes. | LOW | `app/main.py` maps `(ValueError, RuntimeError)` to HTTP 400 in `ask_research_discussion_codex`. | Deferred. This matches the existing paper-chat endpoint behavior and should be changed across both Codex endpoints in a future API error-semantics pass. | Not changed. |

## Verified Claims

- Codex execution failure does not persist partial turns. `ask_research_discussion_codex` runs `_run_codex_exec_prompt` before creating the user message, grounding snapshot, or assistant message.
- `ResearchDiscussionCodexAsk` caps `content` at 5000 characters and `system_prompt` at 4000 characters.
- Project title, goal, and current state are capped in `build_codex_research_discussion_prompt`.
- The frontend avoids duplicate selected-discussion fetching and disables repeated Codex submissions while a request is in flight.
- Paper chat Codex behavior remains compatible after the shared `_prepare_codex_exec` and `_run_codex_exec_prompt` refactor.

## Verification Context

- `env PYTHONPATH=.:.deps python3 -m pytest` -> 60 passed before merge.
- `npm run build` -> passed before merge.
- `git diff --check` -> clean before merge.
