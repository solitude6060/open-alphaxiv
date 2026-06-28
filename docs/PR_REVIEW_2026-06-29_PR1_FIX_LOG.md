# PR Review 2026-06-29 PR1 Fix Log

PR: https://github.com/solitude6060/open-alphaxiv/pull/1

## Summary

OpenCode DeepSeek produced actionable findings. AGY and Claude did not produce
reviews because their lanes were blocked. This fix log records the verified
findings, fixes, and validation commands.

## Fixes

| Finding | Fix | Tests |
|---|---|---|
| API tests bypassed HTTP routing and serialization. | Replaced direct endpoint invocation with ASGI HTTP tests in `tests/test_api.py`; changed the tested handlers in `app/main.py` to async handlers so the test environment does not block on the sync threadpool path. | `tests/test_api.py:44`, `tests/test_api.py:56`, `tests/test_api.py:71` |
| Codex failure branches were untested. | Added timeout, non-zero return code, and empty stdout regression tests. | `tests/test_services.py:126`, `tests/test_services.py:149`, `tests/test_services.py:172` |
| Empty retrieved chunk context produced a weak Codex prompt. | Added an explicit no-chunks message to `build_codex_paper_prompt()`. | `tests/test_services.py:195` |
| Codex status failure could block normal refresh. | Fetch providers and papers independently from Codex status; treat Codex status failure as unavailable Codex only. | `npm run build` |

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py::test_root_endpoint_points_to_api_entrypoints -vv -s` -> 1 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py tests/test_services.py` -> 15 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest` -> 15 passed.
- `npm run build` -> passed.
- `git diff --check` -> passed.

## Deferred

- `scripts/check-codex-docker.sh` redundant check was left unchanged because it
  does not affect correctness.
- Static `auth_modes` remains descriptive metadata because `integration_boundary`
  states that browser OAuth is not provided.
