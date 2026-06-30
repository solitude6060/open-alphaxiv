# PR Review 2026-06-30 PR10 OpenCode DeepSeek

- PR: https://github.com/solitude6060/open-alphaxiv/pull/10
- Base branch: `main`
- Head branch: `feature/research-discussion-codex`
- Reviewed head SHA: `11b04eaeb38e4555e2002049606448a74dcb470b`
- Reviewer command: `opencode run --model opencode/deepseek-v4-flash-free --title pr10-review "$(cat /tmp/pr10_review_prompt.txt)"`
- Raw output: `/tmp/pr10_review_opencode_deepseek.out`

## Verdict

APPROVE.

## Findings

| Finding | Severity | Reviewer Evidence | Triage | Fix Status |
|---|---:|---|---|---|
| RuntimeError maps to HTTP 400 instead of 5xx. | HIGH, noted as pre-existing and non-blocking | Existing paper chat endpoint has the same convention. | Deferred. Keep compatibility in this PR; change both endpoints in a future API error semantics pass. | Not changed. |
| Duplicate selected-discussion GET. | MEDIUM | `refreshResearch` and `selectedDiscussionId` effect could both fetch the same discussion. | Accepted. | Fixed in `6925173`. |
| `ResearchDiscussionCodexAsk.content` had no Pydantic max length. | MEDIUM | `content: str` accepted arbitrary size. | Accepted. | Fixed in `6925173` with `max_length=5000`; `system_prompt` also capped at 4000. |
| Redundant conversation history truncation. | LOW | Caller and formatter both limit to 12 messages. | Deferred. The formatter remains the shared guard; caller truncation documents the turn-specific intent. | Not changed. |
| No test for empty content. | LOW | Content validation was not directly covered. | Deferred. Pydantic and service validation are straightforward; current tests cover disabled and failure paths. | Not changed. |
| No test for empty grounding snapshot fallback. | LOW | Empty context string branch lacks direct test. | Deferred. Existing snapshot construction always returns content for real project state. | Not changed. |

## Verification After Fix

- `env PYTHONPATH=.:.deps python3 -m pytest` -> 60 passed.
- `npm run build` -> passed.
- `git diff --check` -> clean.
