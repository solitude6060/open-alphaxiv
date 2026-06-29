# PR #5 Review Fix Log

- PR: https://github.com/solitude6060/open-alphaxiv/pull/5
- Base branch: `main`
- Head branch: `feature/local-pdf-upload`

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Missing upload size limit. | OpenCode, Codex | HIGH | `app/main.py:155` previously read full request body; arXiv `fetch_binary` already caps at 50 MB. | Fixed. |
| Header-only fake PDF accepted. | Codex | HIGH | `validate_pdf_bytes(...)` previously checked only `%PDF`; success tests used fake bytes. | Fixed. |
| Raw JSON upload errors shown in UI. | OpenCode | MEDIUM | `web/src/main.tsx:337` threw response text directly. | Fixed. |
| Stale `indexing` duplicate upload returned as existing paper. | Codex | MEDIUM | Existing duplicate branch returned any matching row without checking status. | Fixed. |
| Upload double-click while in flight. | OpenCode | LOW | Backend duplicate handling is idempotent. | Deferred. |
| Content-Type header not enforced. | OpenCode | LOW | Byte validation is authoritative. | Skipped. |

## Fixes

- Added `MAX_UPLOAD_PDF_BYTES = 50_000_000`.
- Added API-level `Content-Length` precheck and post-read size check with HTTP 413.
- Added service-level size validation for direct service callers.
- Added `pdfinfo` parseability validation when Poppler is available.
- Changed upload success tests to use a minimal valid PDF fixture.
- Added malformed `%PDF` regression tests for service and API.
- Added oversized upload regression tests for service and API.
- Added stale duplicate upload retry behavior and regression coverage.
- Added frontend FastAPI `detail` extraction for upload errors.

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest` - 36 passed.
- `npm run build` - passed.
- `git diff --check` - passed.

## Remaining Risk

- Browser file-picker end-to-end upload was not fully exercised because existing local Docker services and managed-shell port binding interfered with a clean dev server. The HTTP contract is covered by ASGI tests, and the top-bar upload control was inspected through a Playwright snapshot.
