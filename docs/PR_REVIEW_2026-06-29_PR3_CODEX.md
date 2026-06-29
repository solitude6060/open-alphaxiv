# PR Review 2026-06-29 PR3 Codex

PR: https://github.com/solitude6060/open-alphaxiv/pull/3
Base: `main`
Head: `feature/arxiv-like-paper-reader`
Head SHA reviewed: `30d8520c9740e12f886e954bbb69669f85a0e2b3`

## Reviewer

Command:

```bash
codex exec --model gpt-5.5 "$(cat /tmp/pr3_review_prompt.txt)" > /tmp/pr3_review_codex.out 2>&1
```

Output file: `/tmp/pr3_review_codex.out`

Supplementary fallback output: `/tmp/pr3_review_codex_spark_fallback.out`

## Verdict

REQUEST CHANGES

## Findings

| Finding | Severity | Triage |
|---|---:|---|
| The reader fans out one request per page for lazy text-layer extraction and can duplicate extraction work under concurrent loads. | HIGH | Verified in `web/src/main.tsx` and `app/services.py`; fixed with one all-pages endpoint plus a per-paper single-flight lock. |
| Papers without rendered page images lose all visible reading content. | MEDIUM | Verified in `web/src/main.tsx`; fixed by showing the abstract in the PDF-unavailable state. |
| Poppler bounding-box Y coordinates were claimed to be upside down. | MEDIUM | Rejected after manual verification: page title text renders near the top with the current top-origin mapping. |
| Markdown inline rendering lacks italic support. | LOW | Deferred; not blocking for current Markdown answer rendering. |

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Per-page text-layer fanout and duplicate extraction | codex | HIGH | Browser logs showed page-level text requests before the fix; backend had no per-paper generation lock. | Fixed |
| PDF-unavailable reading content | codex | MEDIUM | Empty page list rendered only an unavailable state. | Fixed |
| Y coordinate inversion | codex | MEDIUM | Manual browser check selected `Attention Is All You Need` near the top of page 1; coordinate math matched the rendered page. | Rejected |
| Italic inline Markdown | codex | LOW | Current renderer covers headings, lists, links, code, bold, blockquotes, tables, and code fences. | Deferred |
