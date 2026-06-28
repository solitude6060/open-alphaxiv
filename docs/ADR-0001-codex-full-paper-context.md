# ADR 0001: Use Full Extracted Paper Text for Codex Paper Q&A

## Status

Accepted

## Context

The product requirements originally state that paper chat must retrieve paper
chunks before generation and show source references. That remains useful for
mock mode, provider debugging, and future models with smaller prompt budgets.

For the local Codex connector, the visible chunk workflow creates a poor reading
experience: the reader sees implementation fragments instead of a paper-like
document, and Codex can work with a larger direct paper context than the MVP
retrieval path was designed for.

Codex context is still finite. The implementation must not assume an unlimited
prompt budget.

## Decision

Codex paper Q&A uses the extracted paper text artifact as the primary prompt
context. The UI no longer displays paper chunks in the reader or under Codex
answers. It displays the paper text and page images instead.

The backend keeps chunking and retrieval for mock mode, local indexing, graph
construction, and diagnostics. Codex mode sends:

- paper metadata
- selected passage text, when present
- selected image region metadata, when present
- extracted paper text, truncated with an explicit marker when it exceeds the
  local prompt budget

Selected image regions identify a page and bounding box. The current Codex
prompt does not include image pixels.

## Consequences

- The reader is closer to a paper-reading workflow and no longer exposes raw
  retrieval chunks as primary content.
- Codex answers can reference the paper broadly instead of only the top retrieved
  chunks.
- Chunk-level citations are not shown for Codex mode until a cleaner citation
  design exists.
- Very long papers may still be truncated before reaching Codex; the prompt
  includes a truncation notice when that happens.
