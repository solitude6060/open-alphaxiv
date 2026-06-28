# PR Review 2026-06-29 PR1 Codex Spark

PR: https://github.com/solitude6060/open-alphaxiv/pull/1
Base: `main`
Head: `feature/codex-paper-chat`
Head SHA reviewed: `e6aac299a0c0996ccb9e274e6bb6b7671b683e46`

## Reviewer

Reviewer: Codex native subagent `019f0f68-4f01-76f3-a139-e6cd6c7a6a42`
Model: `gpt-5.3-codex-spark`
Mode: read-only review

## Verdict

APPROVE

## Findings

| Finding | Severity | Triage |
|---|---:|---|
| Codex subprocess invocation did not catch non-timeout `OSError` failures, so permission or startup errors could return HTTP 500. | MEDIUM | Verified; fixed by converting `OSError` to `RuntimeError` and adding a regression test. |
| `/api/codex/status` advertised `chatgpt_login`, which could imply browser OAuth even though the app only supports host CLI login for Codex. | LOW | Verified; fixed by changing the advertised mode to `host_cli_login` and updating tests. |
| Invalid `answer_mode` had no explicit API contract test. | LOW | Verified; fixed with an HTTP 400 test. |

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Codex subprocess non-timeout startup failure | codex-spark | MEDIUM | `app/services.py` now catches `OSError`; `tests/test_services.py` covers `PermissionError`. | Fixed |
| Misleading `chatgpt_login` status metadata | codex-spark | LOW | `app/main.py` now returns `host_cli_login`; `tests/test_api.py` asserts `chatgpt_login` is absent. | Fixed |
| Missing invalid answer mode API test | codex-spark | LOW | `tests/test_api.py` now asserts invalid `answer_mode` returns HTTP 400. | Fixed |

## Verification After Fixes

- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py tests/test_services.py` -> 18 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest` -> 18 passed.
- `npm run build` -> passed.
- `bash scripts/check-codex-docker.sh` -> passed.
- `OPEN_ALPHAXIV_HOST_NODE_PREFIX=/tmp OPEN_ALPHAXIV_HOST_CODEX_HOME=/tmp docker compose -f docker-compose.yml -f docker-compose.codex.yml config` -> passed.
- `git diff --check` -> passed.

