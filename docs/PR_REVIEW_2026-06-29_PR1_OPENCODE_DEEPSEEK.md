# PR Review 2026-06-29 PR1 OpenCode DeepSeek

PR: https://github.com/solitude6060/open-alphaxiv/pull/1
Base: `main`
Head: `feature/codex-paper-chat`
Head SHA reviewed: `c476bb5da508ac437d123cd263ea38343b740bc3`

## Reviewer

Command:

```bash
opencode run --model opencode/deepseek-v4-flash-free --title pr1-review "$(cat /tmp/pr1_review_prompt.txt)" > /tmp/pr1_review_opencode_deepseek.out 2>&1
```

Output file: `/tmp/pr1_review_opencode_deepseek.out`

## Verdict

APPROVE with advisory notes

## Findings

| Finding | Severity | Triage |
|---|---:|---|
| API endpoint tests bypassed FastAPI routing and response handling. | MEDIUM | Verified in `tests/test_api.py`; fixed by replacing direct endpoint calls with ASGI HTTP tests. |
| Codex timeout, non-zero exit, and empty stdout paths were untested. | MEDIUM | Verified in `app/services.py`; fixed with three regression tests. |
| Empty retrieved chunk context produced an uninformative Codex prompt. | LOW | Verified in `app/services.py`; fixed with an explicit no-chunks prompt line. |
| Codex status fetch failure could block provider and paper loading. | LOW | Verified in `web/src/main.tsx`; fixed by catching Codex status separately. |
| `scripts/check-codex-docker.sh` contains a redundant executable existence check. | LOW | Verified as harmless; skipped because it does not change runtime behavior. |
| Static `auth_modes` includes `chatgpt_login`. | INFO | Verified as descriptive metadata; skipped because the adjacent integration boundary text clarifies that browser OAuth is not provided. |

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| API tests bypass HTTP boundary | opencode-deepseek | MEDIUM | `tests/test_api.py:44`, `tests/test_api.py:56`, `tests/test_api.py:71` now use ASGI HTTP requests. | Fixed |
| Codex failure branches untested | opencode-deepseek | MEDIUM | `tests/test_services.py:126`, `tests/test_services.py:149`, `tests/test_services.py:172` cover timeout, non-zero return code, and empty stdout. | Fixed |
| Empty retrieval prompt | opencode-deepseek | LOW | `app/services.py:732` adds a no-chunks message; `tests/test_services.py:195` covers it. | Fixed |
| Codex status blocks refresh | opencode-deepseek | LOW | `web/src/main.tsx:147` now isolates `/api/codex/status` failure. | Fixed |
| Redundant executable check | opencode-deepseek | LOW | Script behavior remains correct. | Skipped; no user-visible defect. |
| Static auth modes | opencode-deepseek | INFO | `app/main.py:116` and `app/main.py:117` clarify the boundary. | Skipped; documentation metadata only. |

## Verification After Fixes

- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py tests/test_services.py` -> 15 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest` -> 15 passed.
- `npm run build` -> passed.
- `git diff --check` -> passed.

