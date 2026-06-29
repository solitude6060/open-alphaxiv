# Local PDF Upload Plan

## Goal

Let a researcher import a local PDF file directly from the browser and read it
with the same PDF page rendering, selectable text layer, Markdown export,
library listing, and paper chat behavior used by arXiv imports.

## First-Principles Check

The user need is not "multipart form support"; it is "make a local paper file
usable in the reader and Ask Paper flow." The minimum durable system capability
is therefore:

- Store uploaded PDF bytes as the canonical local artifact.
- Create a `papers` row with `source_type = upload`.
- Reuse the existing PDF ingestion pipeline for text extraction, page images,
  page text layers, Markdown, chunks, and graph construction.
- Keep the PDF selectable and queryable in the same reader UI.

## Scope

In this PR:

- Add a backend upload endpoint for raw `application/pdf` request bodies.
- Add `PaperService.ingest_uploaded_pdf(...)` with content-hash de-duplication.
- Refactor arXiv ingestion to share the PDF artifact and indexing pipeline.
- Add a compact web upload control beside the arXiv import field.
- Update README and SPEC to document the upload path.

Out of scope:

- Batch uploads.
- Persistent background jobs.
- OCR for scanned PDFs.
- Cloud object storage.
- Project-level research notes and experiment tracking. Those are later PRs in
  `docs/RESEARCH_WORKSPACE_PLAN.md`.

## API Contract

`POST /api/papers/upload`

- Request body: raw PDF bytes.
- Headers:
  - `Content-Type: application/pdf`
  - `X-Filename: <original browser filename>` optional.
- Query:
  - `filename` optional original browser filename.
  - `title` optional display title override.
- Response: existing paper shape.

The endpoint deliberately avoids a new multipart dependency. Browser upload
still works because `fetch` can send a `File` object as the request body.

## Tests First

Backend service tests:

- Uploading valid PDF bytes creates a ready paper with `source_type = upload`.
- The uploaded PDF is stored as an artifact.
- Text, page image, page text layer, chunks, and graph data are produced.
- Uploading identical bytes returns the existing paper.
- Non-PDF bytes are rejected.

HTTP API tests:

- Raw PDF upload returns a ready upload paper.
- Non-PDF upload returns HTTP 400.

Frontend verification:

- `npm run build` must pass.
- Upload UI must preserve the existing top bar layout and selected paper flow.

## Acceptance Criteria

- A local PDF can be selected in the browser and imported without an arXiv URL.
- Imported local PDFs appear in the paper library.
- The reader shows rendered PDF pages and selectable text when Poppler output is
  available.
- Ask Paper can use the uploaded paper context.
- No new dependency is introduced for this PR.
