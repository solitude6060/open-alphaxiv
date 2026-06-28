# PR Review 2026-06-29 PR1 Claude

PR: https://github.com/solitude6060/open-alphaxiv/pull/1
Base: `main`
Head: `feature/codex-paper-chat`
Head SHA reviewed: `99472904201e5cf760d6943fa5ff58071d7d8642`

## Reviewer

Command:

```bash
claude -p "$(cat /tmp/pr1_review_prompt.txt)" > /tmp/pr1_review_claude.out 2>&1
```

Output file: `/tmp/pr1_review_claude.out`

## Verdict

REQUEST CHANGES

The first Claude attempt stalled. A later retry with the same
`triple-review` prompt completed after validating that `claude -p "hello"`
worked in non-interactive mode.

## Findings

| Finding | Severity | Triage |
|---|---:|---|
| `async def` request handlers moved blocking work onto the event loop. | HIGH | Verified in `app/main.py`; fixed by offloading `ingest_paper` and `ask` through `asyncio.to_thread`. |
| Real `codex exec` flags are not checked by automated tests. | MEDIUM | Verified; fixed setup-time compatibility check in `scripts/check-codex-docker.sh`. |
| Host Codex home mount is writable. | LOW | Verified; documented intentionally writable mount in `README.md`. |
| Codex subprocess default `cwd` exposes the app root under read-only sandbox. | LOW | Verified; fixed by using an isolated temporary directory by default. |
| `codex_stderr_preview` is returned to the client. | LOW | Verified; skipped for this PR because it is capped diagnostic metadata and useful for local setup debugging. |
| `/api/codex/status` mixes closure settings with fresh credential checks. | LOW | Verified; skipped because process env is static in normal runtime and the behavior does not affect the current PR. |
| Setup script redundancy note was imprecise. | LOW | Verified; superseded by adding explicit required-flag checks. |

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Blocking work in async handlers | claude | HIGH | `app/main.py` uses `asyncio.to_thread()` for `service().ingest_paper` and `service().ask`. | Fixed |
| Codex CLI flags unverified | claude | MEDIUM | `scripts/check-codex-docker.sh` now checks `codex exec --help` for `--ephemeral`, `--sandbox`, and `--skip-git-repo-check`. | Fixed |
| Writable host Codex home mount | claude | LOW | `README.md` now documents that the mount is writable and recommends a dedicated Codex home when needed. | Fixed by documentation |
| Codex subprocess app-root read surface | claude | LOW | `app/services.py` now uses `tempfile.TemporaryDirectory(prefix="open-alphaxiv-codex-")` by default; `tests/test_services.py` covers it. | Fixed |
| `codex_stderr_preview` returned to client | claude | LOW | Field is limited to 500 chars and supports local debugging. | Skipped for this PR |
| Status settings consistency | claude | LOW | Process env is static in normal runtime. | Skipped for this PR |
