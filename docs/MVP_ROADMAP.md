# MVP and Roadmap

## Delivery Strategy

The first implementation should be a local Docker application with a narrow but
complete paper workflow:

1. Configure an OpenAI-compatible provider.
2. Ingest one arXiv paper.
3. Convert and index it.
4. Ask cited questions.
5. Build a related-paper graph.
6. Bookmark, tag, and export notes.

Everything outside that loop is roadmap scope.

## MVP Scope

### User Experience

- Local web UI.
- Paper library.
- Paper detail page.
- Paper chat panel with citations.
- Literature graph page with related, prior, and derivative views.
- Settings page for model providers.
- Processing status and error panels.

### Backend

- FastAPI application.
- Background worker.
- PostgreSQL persistence.
- Redis queue.
- Local object storage through mounted volume or S3-compatible service.
- Provider adapter for OpenAI-compatible generation.
- Provider adapter for OpenAI-compatible embeddings.
- arXiv metadata and PDF ingestion.
- Semantic Scholar metadata connector for graph building.

### Retrieval and Graphs

- Markdown chunking.
- Embedding retrieval.
- Entity extraction baseline.
- Single-paper graph for retrieval expansion.
- Literature graph scoring:
  - direct references
  - direct citations
  - co-citation
  - bibliographic coupling
  - abstract similarity when available

### Docker

- `docker-compose.yml`
- `Dockerfile.web`
- `Dockerfile.api`
- `Dockerfile.worker`
- `.env.example`
- Health checks for API, worker, database, Redis, and provider configuration.

## MVP Exit Criteria

| Requirement | Evidence Required |
| --- | --- |
| Docker local boot | `docker compose up` starts all MVP services. |
| Provider setup | Health check succeeds against an OpenAI-compatible endpoint. |
| Paper ingestion | arXiv paper reaches `ready` status with PDF, Markdown, chunks, and embeddings stored. |
| Paper chat | User asks a question and receives a streamed or non-streamed answer with citations. |
| Retrieval diagnostics | API exposes selected chunks, scores, and provider metadata for a chat answer. |
| Literature graph | Seed paper graph renders at least 20 nodes when metadata is available. |
| Prior and derivative views | Graph can filter older cited works and newer citing works. |
| Bookmarks and tags | User can persist and filter them. |
| Export | User can export summary and notes as Markdown. |
| Tests | Unit, integration, and one end-to-end test cover the main flow. |

## Phase Plan

### Phase 0: Repository Bootstrap

Deliverables:

- Project skeleton.
- Docker Compose baseline.
- `.env.example`.
- Database migrations.
- Test framework.
- CI or local verification commands.

Exit criteria:

- Empty app boots.
- API health endpoint works.
- Web UI can call API health endpoint.
- Database migration runs.

### Phase 1: Provider Abstraction

Deliverables:

- Provider config model.
- OpenAI-compatible generation adapter.
- OpenAI-compatible embedding adapter.
- Provider health checks.
- Secret redaction in logs.

Exit criteria:

- Mock provider tests pass.
- Real provider smoke test can be run manually with `.env`.
- Frontend settings page can create and test a provider.

### Phase 2: Paper Ingestion

Deliverables:

- arXiv URL normalization.
- Metadata fetch.
- PDF download.
- PDF-to-Markdown conversion.
- Chunking.
- Artifact storage.
- Ingestion job UI.

Exit criteria:

- A known arXiv paper can be processed to Markdown and chunks.
- Failed steps show actionable status.
- Retrying does not duplicate paper records.

### Phase 3: Retrieval and Paper Chat

Deliverables:

- Embedding generation.
- Vector retrieval.
- Entity extraction baseline.
- Single-paper graph expansion.
- Chat endpoint.
- Citation renderer.
- Retrieval diagnostics endpoint.

Exit criteria:

- Mocked model chat integration test passes.
- Answer citations point to stored chunks.
- UI displays source chunks.

### Phase 4: Literature Graph

Deliverables:

- Semantic Scholar connector.
- Candidate graph builder.
- Scoring for prior, derivative, and related papers.
- Graph API.
- Interactive graph UI.

Exit criteria:

- Seed paper graph builds from metadata.
- UI filters related, prior, and derivative views.
- Node detail panel shows why a paper is connected.

### Phase 5: Library Workflow

Deliverables:

- Bookmarks.
- Tags.
- Search and filters.
- Generated summary artifacts.
- Markdown export.

Exit criteria:

- User can manage a small reading library locally.
- Export includes title, metadata, summary, notes, citations, and graph snapshot
  reference.

## Post-MVP Roadmap

### V0.2: Better Reading Experience

- PDF side-by-side with Markdown.
- Section-aware navigation.
- Figure and table extraction.
- Equation-aware chunking.
- Multiple summary formats.
- Reading progress.

### V0.3: Advanced Literature Discovery

- Multi-hop graph expansion.
- Community detection.
- Saved graph snapshots.
- Graph diff over time.
- Author and venue filters.
- Better influence and recency ranking.

### V0.4: Local-First Collaboration

- Multi-user local deployment.
- Shared libraries.
- Role-based access.
- Comment threads.
- Shared graph views.

### V0.5: Agent Integrations

- GitHub OAuth repository linking.
- GitHub MCP connector.
- Copilot SDK connector where local credentials and subscription allow it.
- Codex connector for paper-to-code planning and implementation notes.
- Agent run audit trail.

### V0.6: alphaXiv-Style Discovery

- Personalized feed.
- arXiv category watchers.
- Trending papers by local and external signals.
- Browser extension.
- Audio summaries.
- Public share pages for self-hosted deployments.

## Implementation Risks

| Risk | Mitigation |
| --- | --- |
| PDF conversion quality | Keep converter pluggable; store raw PDF and Markdown; expose conversion diagnostics. |
| Provider incompatibility | Implement separate adapters for Responses and Chat Completions; add provider health checks. |
| Semantic Scholar rate limits | Cache metadata; queue graph builds; support API key configuration. |
| Graph ranking too weak | Store scoring components and explanations; improve algorithm iteratively. |
| Secret leakage | Redact logs; keep secrets server-side; add tests for config serialization. |
| Copilot/Codex availability | Treat as optional connectors; require capability checks and documented user credentials. |

## First Implementation Backlog

1. Create app skeleton and Docker Compose.
2. Add database schema and migrations for papers, artifacts, chunks, providers,
   chat, and graph tables.
3. Implement provider adapters and health checks.
4. Implement arXiv ingestion with fixture tests.
5. Implement PDF conversion and chunking.
6. Implement embedding storage and vector retrieval.
7. Implement cited chat with mocked provider tests.
8. Implement Semantic Scholar connector and literature graph scoring.
9. Implement web UI for library, settings, paper detail, chat, and graph.
10. Add end-to-end test for the MVP loop.

