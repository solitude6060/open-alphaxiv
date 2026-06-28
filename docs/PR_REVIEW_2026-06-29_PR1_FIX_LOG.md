# PR Review 2026-06-29 PR1 Fix Log

PR: https://github.com/solitude6060/open-alphaxiv/pull/1

## Summary

OpenCode DeepSeek produced actionable findings. AGY remained blocked by Google
OAuth timeout. Claude initially stalled, then completed on retry and requested
changes. This fix log records the verified findings, fixes, and validation
commands.

## Fixes

| Finding | Fix | Tests |
|---|---|---|
| API tests bypassed HTTP routing and serialization. | Replaced direct endpoint invocation with ASGI HTTP tests in `tests/test_api.py`. The tested handlers remain async but blocking service calls are offloaded with `asyncio.to_thread()` so production request handling does not block the event loop. | `tests/test_api.py:44`, `tests/test_api.py:56`, `tests/test_api.py:71` |
| Codex failure branches were untested. | Added timeout, non-zero return code, and empty stdout regression tests. | `tests/test_services.py:126`, `tests/test_services.py:149`, `tests/test_services.py:172` |
| Codex subprocess default working directory exposed the app root to the read-only sandbox. | Run Codex in an isolated temporary directory unless a test or caller explicitly supplies `cwd`. | `tests/test_services.py:195` |
| Empty retrieved chunk context produced a weak Codex prompt. | Added an explicit no-chunks message to `build_codex_paper_prompt()`. | `tests/test_services.py:223` |
| Codex status failure could block normal refresh. | Fetch providers and papers independently from Codex status; treat Codex status failure as unavailable Codex only. | `npm run build` |
| Codex CLI flag compatibility was only manually verified. | Added `codex exec --help` checks for required paper-chat flags in `scripts/check-codex-docker.sh`. | `bash scripts/check-codex-docker.sh` |
| Host Codex home mount is writable from the API container. | Documented that this is intentional because Codex may update local state under `CODEX_HOME`; recommended using a dedicated Codex home when host state isolation matters. | README review |
| Codex subprocess non-timeout startup failures could bubble as HTTP 500. | Convert `OSError` from `subprocess.run()` into `RuntimeError` so the API handler returns the existing HTTP 400 error contract. | `tests/test_services.py` |
| `auth_modes` exposed `chatgpt_login` and could imply browser OAuth. | Rename the status metadata to `host_cli_login`; assert `chatgpt_login` is absent. | `tests/test_api.py` |
| Invalid `answer_mode` lacked an explicit HTTP contract test. | Added an ASGI HTTP test that invalid answer modes return HTTP 400 with the service error message. | `tests/test_api.py` |

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py::test_chat_messages_accepts_codex_answer_mode_over_http -vv -s` -> 1 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py tests/test_services.py` -> 18 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest` -> 18 passed.
- `npm run build` -> passed.
- `bash scripts/check-codex-docker.sh` -> passed.
- `OPEN_ALPHAXIV_HOST_NODE_PREFIX=/tmp OPEN_ALPHAXIV_HOST_CODEX_HOME=/tmp docker compose -f docker-compose.yml -f docker-compose.codex.yml config` -> passed.
- `git diff --check` -> passed.

## Deferred

- Static `auth_modes` remains descriptive metadata because `integration_boundary`
  states that browser OAuth is not provided.
- `codex_stderr_preview` remains in the local HTTP response for setup debugging;
  it is capped at 500 normalized characters and is not displayed by the UI.
