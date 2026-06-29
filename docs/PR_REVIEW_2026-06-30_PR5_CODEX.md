# PR #5 Review - Codex

- PR: https://github.com/solitude6060/open-alphaxiv/pull/5
- Base branch: `main`
- Head branch: `feature/local-pdf-upload`
- Head SHA reviewed: `ed70453`
- Reviewer command: `codex exec --sandbox read-only --skip-git-repo-check "$(cat /tmp/pr5_review_prompt.txt)"`
- Output file: `/tmp/pr5_review_codex.out`

## Verdict

REQUEST CHANGES before merge.

## Findings

| Finding | Severity | Evidence | Triage |
|---|---:|---|---|
| Header-only `%PDF` payloads could be accepted and marked `ready`. | HIGH | `validate_pdf_bytes(...)` only checked the magic prefix, while `_index_paper_artifacts(...)` marked papers ready even if parsing produced no readable pages. | Fixed. Added `pdfinfo` parseability validation and regression tests for header-only PDFs. |
| Upload endpoint had no max size. | HIGH | `request.body()` read all bytes and the service wrote them without cap. | Fixed. Added 50 MB cap, HTTP 413, and service/API tests with a monkeypatched low limit. |
| Stale `indexing` upload rows could poison future duplicate uploads. | MEDIUM | Existing-row branch returned any matching upload row by content hash. | Fixed. Ready duplicates return immediately; non-ready duplicates are deleted and retried; unique-race fallback re-queries existing row. |
| Upload success tests used fake PDF bytes under monkeypatched Poppler output. | LOW | Tests proved routing but not parseability. | Fixed. Upload success tests now use a minimal valid PDF fixture. |

## Verified Claims

- `POST /api/papers/upload` uses raw request bytes and adds no multipart dependency.
- Uploaded papers use `source_type = 'upload'` and SHA-256 `source_id`.
- arXiv markdown source labeling remains `arXiv:<id>`.
- Uploads and arXiv imports share the PDF artifact, Markdown, chunk, page image, page text layer, and graph indexing path.
