# PR #5 Review - OpenCode DeepSeek

- PR: https://github.com/solitude6060/open-alphaxiv/pull/5
- Base branch: `main`
- Head branch: `feature/local-pdf-upload`
- Head SHA reviewed: `ed70453`
- Reviewer command: `opencode run --model opencode/deepseek-v4-flash-free --title pr5-review "$(cat /tmp/pr5_review_prompt.txt)"`
- Output file: `/tmp/pr5_review_opencode_deepseek.out`

## Verdict

REQUEST CHANGES before merge.

## Findings

| Finding | Severity | Evidence | Triage |
|---|---:|---|---|
| Upload endpoint had no request-body size limit. | MEDIUM | `app/main.py:155` read the entire request body without enforcing the 50 MB cap used by arXiv downloads. | Fixed. Added `MAX_UPLOAD_PDF_BYTES`, `Content-Length` precheck, post-read size check, HTTP 413, and regression tests. |
| Upload failure displayed raw JSON in the frontend error banner. | MEDIUM | `web/src/main.tsx:337` read the response as text and threw the JSON string. | Fixed. Added `errorMessageFromResponse(...)` to extract FastAPI `detail`. |
| Upload button has no in-flight disabled state. | LOW | Existing arXiv import has the same limitation; backend upload deduplication makes duplicate clicks idempotent. | Deferred. Not a correctness blocker for PR #5. |
| Upload endpoint does not validate `Content-Type`. | LOW | Content bytes are checked directly. | Skipped. Byte validation is the authoritative check. |

## Verified Claims

- `source_type` and `source_id` are stored on paper rows.
- Upload deduplication uses SHA-256 content hash.
- arXiv imports still use `source_type = 'arxiv'`.
- The upload path and arXiv path share `_index_paper_artifacts(...)`.
- No new dependency was added.
