# PR #9 Local Review

## Scope

PR #9: `feature/research-search-dashboard` into
`feature/research-discussions`

Reviewed feature:

- local research dashboard
- typed research search API
- Research panel dashboard/search UI
- tests and docs for the dashboard/search layer

## External Review Context

Claude was not re-run for PR #9 because PR #8 review attempts showed the local
Claude CLI could answer a minimal ping but timed out with 0-byte output on both
repo-reading and embedded-diff review prompts.

## Findings

No blocking findings found in local review.

## Local Review Checks

- Search is bounded to 100 rows maximum through the service `limit` clamp.
- Search uses parameterized SQL values for user query text and project scope.
- Empty query returns an empty result list instead of scanning all rows.
- Project-scoped search validates the project and returns 404 through the HTTP
  layer when the project does not exist.
- Dashboard counts and active project summaries use deterministic SQLite
  aggregates without background indexing.
- Frontend search runs only on explicit action instead of every keystroke.

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest` -> 45 passed
- `npm run build` from `web/` -> passed
- `git diff --check` -> passed
- Browser/API smoke on API `18003` and web `3313`:
  - `GET /api/research/dashboard` -> 200 with expected counts
  - `GET /api/research/search?q=retrieval&project_id=1` -> 200 with typed
    note/run/discussion/message/snapshot results
  - Research panel rendered `Status dashboard` and `Search research`
  - Search UI displayed `Found 5 research results`
  - Browser console had no functional errors

## Residual Risks

- Large local databases may need full-text indexes or pagination later.
- Ranking is deterministic by table order and recency, not semantic relevance.
- This PR does not index remote codebases or external files.
