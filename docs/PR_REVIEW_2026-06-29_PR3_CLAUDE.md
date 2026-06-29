# PR Review 2026-06-29 PR3 Claude

PR: https://github.com/solitude6060/open-alphaxiv/pull/3
Base: `main`
Head: `feature/arxiv-like-paper-reader`
Head SHA reviewed: `30d8520c9740e12f886e954bbb69669f85a0e2b3`

## Reviewer

Command:

```bash
claude -p "$(cat /tmp/pr3_review_prompt.txt)" > /tmp/pr3_review_claude.out 2>&1
```

Output file: `/tmp/pr3_review_claude.out`

## Verdict

REQUEST CHANGES

## Findings

| Finding | Severity | Triage |
|---|---:|---|
| Markdown rendering can loop forever on malformed block starts such as `- `, `# `, or `1. `. | HIGH | Verified in `web/src/main.tsx`; fixed by consuming the current line before paragraph continuation scanning. |
| The page text-layer endpoint can run expensive PDF extraction on the event loop. | MEDIUM | Verified in `app/main.py`; fixed by offloading text-layer generation through `asyncio.to_thread()`. |
| Invalid page numbers can return an empty text layer instead of HTTP 404. | MEDIUM | Verified in `app/services.py`; fixed by validating the page image exists before returning page text. |

## Triage

| Finding | Source | Severity | Verified Evidence | Action |
|---|---|---:|---|---|
| Malformed Markdown parser loop | claude | HIGH | Paragraph fallback previously did not advance `index` before scanning continuation lines. | Fixed |
| Blocking lazy text-layer extraction | claude | MEDIUM | `paper_page_text_layer()` can generate text layers when no artifact exists. | Fixed |
| Missing invalid-page 404 | claude | MEDIUM | `paper_page_text_layer(999)` could return an empty fallback. | Fixed |
