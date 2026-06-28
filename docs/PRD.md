# Product Requirements Document

## Product Name

Working name: Open AlphaXiv Local

## Problem

Researchers and builders need a local-first web application that can ingest
arXiv papers, explain them, answer questions with source-grounded context, and
map related literature. Existing tools split this workflow across:

- alphaXiv-style discovery and paper explanation.
- Connected Papers-style literature graph exploration.
- Ad hoc local scripts for PDF conversion and retrieval-augmented generation.

The requested product should combine these workflows into one Docker-deployable
local web application with configurable model providers, including
OpenAI-compatible APIs and optional Codex or GitHub Copilot integrations where
officially supported.

## Target Users

| User | Need |
| --- | --- |
| Independent researcher | Build a local library of papers, understand papers quickly, and explore related work. |
| Applied machine learning engineer | Trace methods, citations, implementation clues, and code links across a paper set. |
| Graduate student | Build reading lists, identify prior and derivative works, and export notes. |
| Local-first operator | Keep papers and notes on local infrastructure while using configurable model APIs. |

## Goals

- Provide a local alphaXiv-like paper reading and explanation interface.
- Provide a Connected Papers-like graph for literature discovery.
- Support Docker-based local deployment.
- Support OpenAI-compatible LLM APIs for generation and embeddings.
- Support optional GitHub OAuth for GitHub account and repository workflows.
- Define a safe extension boundary for GitHub Copilot SDK, GitHub MCP, and
  OpenAI Codex agent integrations.
- Preserve evidence: every model answer should cite retrieved paper chunks or
  metadata sources.

## Non-Goals for MVP

- Public multi-tenant hosting.
- Billing, subscriptions, or paid feature gating.
- Full alphaXiv clone parity.
- Full Connected Papers corpus-scale ranking.
- Browser extension.
- Audio generation.
- Automatic use of private Copilot or Codex APIs outside documented support.
- Replacing Semantic Scholar, arXiv, or publisher metadata licensing terms.

## Primary User Stories

1. As a user, I can submit an arXiv URL and see ingestion progress.
2. As a user, I can open a processed paper and read metadata, abstract,
   generated summary, sections, chunks, and extracted entities.
3. As a user, I can ask questions about the paper and receive answers with
   source citations to chunks or sections.
4. As a user, I can see a graph of related papers around a seed paper.
5. As a user, I can switch graph views between related papers, prior works, and
   derivative works.
6. As a user, I can bookmark papers and tag them for later.
7. As a user, I can configure a local or hosted OpenAI-compatible endpoint for
   generation and embeddings.
8. As a user, I can verify provider health before processing papers.
9. As a user, I can export notes, summaries, citations, and graph snapshots.
10. As an advanced user, I can connect GitHub OAuth for repository and identity
    workflows, and later enable Copilot SDK or Codex connectors if my plan and
    local credentials support them.

## Functional Requirements

### Paper Ingestion

- Accept arXiv abstract URLs and PDF URLs.
- Normalize arXiv identifiers and versions.
- Download PDFs into local object storage.
- Convert PDFs to Markdown.
- Preserve section headings, equations where possible, figure captions, tables,
  references, and page anchors when extraction supports them.
- Store ingestion status:
  - `queued`
  - `downloading`
  - `converting`
  - `chunking`
  - `indexing`
  - `ready`
  - `failed`
- Capture failure reason and retry eligibility.

### Paper Library

- List papers with title, authors, date, source, tags, bookmark status,
  processing status, and summary.
- Search by title, author, abstract, tags, arXiv ID, and local notes.
- Filter by status, tag, bookmark, source, and date.
- Support local-only user accounts or single-user mode.

### Paper Understanding

- Generate:
  - Short summary.
  - Contribution bullets.
  - Method overview.
  - Assumptions and limitations.
  - Reproducibility checklist.
  - Related-code links when available from metadata.
- Store generated artifacts with provider, model, prompt version, and source
  chunk IDs.

### Paper Chat

- Chat must retrieve paper chunks before generation.
- Answers must include source references.
- Chat must support streaming output when provider supports it.
- Chat must expose retrieval diagnostics in a developer panel:
  - selected chunks
  - chunk scores
  - graph path or entity match
  - provider model
  - token estimates

### Single-Paper Knowledge Graph

- Extract entity nodes from converted text.
- Store text chunk nodes.
- Store entity-to-entity and entity-to-chunk edges.
- Store edge type, score, and supporting chunk references.
- Use the graph to improve retrieval over plain vector similarity.

### Literature Graph

- Seed from an arXiv ID, DOI, Semantic Scholar paper ID, or local paper.
- Fetch paper metadata, references, citations, authors, venues, year, abstract,
  and open-access links when available.
- Generate candidate related papers from:
  - references
  - citations
  - shared references
  - shared citations
  - embedding similarity when abstracts are available
- Compute edge scores using:
  - bibliographic coupling
  - co-citation
  - citation direction
  - semantic similarity
  - recency and influence signals
- Provide views:
  - Related papers
  - Prior works
  - Derivative works
- Render an interactive force-directed graph.
- Selecting a node must show metadata and the path or strongest connection to
  the seed paper.

### Provider Configuration

- Support OpenAI-compatible generation providers with:
  - base URL
  - API key or bearer token
  - model name
  - wire API: Responses or Chat Completions
  - streaming on/off
  - timeout and retry settings
- Support embedding providers with:
  - base URL
  - API key or bearer token
  - model name
  - embedding dimension
- Support local endpoints such as Ollama, LM Studio, vLLM, LiteLLM, or OpenAI
  official API when configured by the user.
- Store secrets outside client-side code.
- Provide health checks before use.

### GitHub, Copilot, and Codex Integrations

MVP:

- GitHub OAuth for identity and optional repository metadata access.
- GitHub repository links associated with papers.
- Local configuration fields for future Copilot SDK and Codex connectors.

Post-MVP:

- GitHub MCP connector for repository-aware tasks.
- Copilot SDK connector where the user's environment supports GitHub OAuth or
  BYOK.
- Codex task connector for generating implementation plans or code-reading
  notes from paper context, subject to official availability and subscription
  requirements.

## Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| Deployment | Must run through Docker Compose on a single machine. |
| Privacy | Papers, notes, graph data, and chat history are local by default. |
| Provider safety | Secrets never reach the frontend bundle or logs. |
| Observability | Ingestion, retrieval, generation, provider calls, and graph builds emit structured logs. |
| Reproducibility | Generated outputs store model, provider, prompt version, source IDs, and timestamps. |
| Resilience | Failed ingestion jobs can be retried without duplicating paper records. |
| Portability | Application state can be backed up from named Docker volumes. |
| Licensing | Metadata and corpus source terms must be documented per connector. |

## MVP Acceptance Criteria

- `docker compose up` starts web, API, worker, database, and retrieval services.
- A user can process at least one arXiv paper from URL to ready status.
- A user can ask a question and receive a cited answer from retrieved chunks.
- A user can view a local literature graph for the paper with at least related,
  prior, and derivative groupings.
- A user can configure an OpenAI-compatible provider and pass a health check.
- A user can bookmark and tag a paper.
- The UI exposes enough processing diagnostics to debug failed ingestion.
- Documentation describes the limitation of Copilot and Codex integrations.

## Open Questions

- Should the first implementation prioritize FastAPI and Next.js to align with
  `alphaxiv-open`, or use a different stack already preferred by the eventual
  repository?
- Should graph storage use PostgreSQL tables only for MVP, or introduce a graph
  database later?
- Which local model endpoint should be used for first-class local testing:
  Ollama, LM Studio, vLLM, or LiteLLM?
- Should paper notes be Markdown files on disk, database records, or both?

