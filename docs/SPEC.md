# Technical Specification

## Scope

Build a local-first web application that combines:

- alphaXiv-style paper discovery, summaries, bookmarking, and paper chat.
- Connected Papers-style literature graph exploration.
- Provider-neutral model integration through OpenAI-compatible APIs.
- Optional GitHub OAuth, Copilot SDK, GitHub MCP, and Codex connectors.
- Docker Compose deployment.

This specification covers the intended system contract. It does not implement
every roadmap item yet, but the implemented MVP follows this contract.

## Reference Architecture

MVP services:

| Service | Responsibility |
| --- | --- |
| `web` | Browser UI for library, paper detail, chat, graph, settings, and exports. |
| `api` | HTTP API, authentication, provider routing, paper metadata, chat orchestration. |
| `worker` | Long-running jobs: PDF download, conversion, chunking, indexing, graph building, summaries. |
| `postgres` | Primary relational store. Use `pgvector` if available for MVP embeddings. |
| `redis` | Queue and short-lived job status cache. |
| `object-storage` | Local S3-compatible storage or mounted volume for PDFs, Markdown, artifacts, and exports. |

Optional services:

| Service | When Needed |
| --- | --- |
| `qdrant` | If `pgvector` is not sufficient for retrieval scale. |
| `lightrag` or `minirag` | If using a dedicated graph retrieval server instead of in-process retrieval. |
| `mcp-proxy` | If exposing local paper tools to GitHub Copilot or other MCP clients. |

## Deployment Contract

The default Docker Compose profile should expose:

- Web UI: `http://localhost:3100`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- PostgreSQL: internal only by default
- Redis: internal only by default
- Object storage console: optional admin profile only

Secrets are supplied through `.env` or Docker secrets. The frontend receives
only public configuration such as `NEXT_PUBLIC_API_URL`.

## Technology Baseline

Recommended MVP stack:

- Frontend: Next.js with React and TypeScript.
- Backend: FastAPI with Python.
- Jobs: Redis Queue, Celery, Dramatiq, or Arq. Choose one during implementation
  based on repository preference.
- Database: PostgreSQL with SQLAlchemy or SQLModel migrations.
- Vector storage: `pgvector` for MVP.
- PDF conversion: Markitdown first, with a pluggable converter interface.
- Graph layout: client-side force simulation for small graphs; server stores
  nodes and edges.

Rationale:

- FastAPI and Markitdown align with the `alphaxiv-open` reference.
- PostgreSQL keeps MVP Docker deployment simpler than adding both a graph
  database and a vector database.
- Provider abstraction prevents a hard dependency on Gemini or any single model.

## Core Domain Model

### Paper

Fields:

- `id`
- `source_type`: `arxiv`, `doi`, `semantic_scholar`, `upload`
- `source_id`
- `arxiv_id`
- `doi`
- `semantic_scholar_id`
- `title`
- `abstract`
- `authors`
- `published_at`
- `updated_at`
- `venue`
- `pdf_url`
- `landing_url`
- `status`
- `status_reason`
- `created_at`
- `updated_at`

Constraints:

- `(source_type, source_id)` is unique.
- `arxiv_id` is unique when present.

### PaperArtifact

Stores local file references and generated artifacts.

Fields:

- `id`
- `paper_id`
- `artifact_type`: `pdf`, `pdf_text`, `page_image`, `page_text_layers`,
  `markdown`, `summary`, `notes`, `graph_snapshot`, `export`
- `storage_uri`
- `content_hash`
- `metadata_json`
- `created_at`

### PaperChunk

Fields:

- `id`
- `paper_id`
- `section_path`
- `page_start`
- `page_end`
- `chunk_index`
- `text`
- `token_count`
- `embedding`
- `content_hash`

### EntityNode

Fields:

- `id`
- `paper_id`
- `name`
- `normalized_name`
- `entity_type`
- `description`
- `score`

### PaperGraphEdge

Single-paper graph edge.

Fields:

- `id`
- `paper_id`
- `source_node_type`
- `source_node_id`
- `target_node_type`
- `target_node_id`
- `edge_type`
- `score`
- `supporting_chunk_ids`
- `description`

### LiteratureNode

Cross-paper graph node.

Fields:

- `id`
- `paper_id`
- `external_source`
- `external_id`
- `title`
- `authors`
- `year`
- `venue`
- `abstract`
- `citation_count`
- `influential_citation_count`
- `is_open_access`
- `url`

### LiteratureEdge

Cross-paper graph edge.

Fields:

- `id`
- `seed_paper_id`
- `source_literature_node_id`
- `target_literature_node_id`
- `edge_type`: `cites`, `cited_by`, `co_cited`, `bibliographic_coupling`,
  `semantic_similarity`
- `score`
- `explanation`
- `metadata_json`

### ChatSession and ChatMessage

Chat sessions are scoped to a paper or paper set.

Message metadata must include:

- provider
- model
- prompt version
- user-configured Codex system prompt preview when supplied
- retrieved chunk IDs
- retrieved literature node IDs
- token counts when available
- latency
- error state

### ProviderConfig

Fields:

- `id`
- `name`
- `provider_kind`: `generation`, `embedding`, `agent`, `github`
- `provider_type`: `openai_compatible`, `openai`, `copilot_sdk`,
  `github_oauth`, `github_mcp`, `codex_cli`, `ollama`, `lmstudio`, `custom`
- `base_url`
- `model`
- `wire_api`: `responses`, `chat_completions`, `embeddings`, `sdk`, `mcp`
- `secret_ref`
- `settings_json`
- `is_default`
- `health_status`
- `last_checked_at`

### ResearchProject

Persistent research workspace scoped to a research direction.

Fields:

- `id`
- `title`
- `slug`
- `status`: `active`, `paused`, `completed`, `archived`
- `goal`
- `current_state`
- `created_at`
- `updated_at`

Constraints:

- `slug` is unique.
- UI archive actions update `status`; they do not hard-delete projects.

### ResearchQuestion

Fields:

- `id`
- `project_id`
- `question`
- `status`: `open`, `investigating`, `answered`, `abandoned`
- `current_answer`
- `created_at`
- `updated_at`

### ResearchNote

Fields:

- `id`
- `project_id`
- `title`
- `body_markdown`
- `note_type`: `idea`, `question`, `summary`, `experiment_note`, `decision`,
  `todo`, `meeting`, `literature_note`
- `status`: `draft`, `active`, `resolved`, `archived`
- `tags_json`
- `created_at`
- `updated_at`

### ResearchLink

Evidence link owned by a research note or future discussion message.

Fields:

- `id`
- `project_id`
- `note_id`
- `discussion_message_id`
- `link_type`: `paper`, `paper_passage`, `paper_region`, `chat_message`,
  `code_path`, `experiment_run`, `experiment_artifact`, `external_url`
- `relation`: `supports`, `contradicts`, `extends`, `implements`, `cites`,
  `mentions`, `questions`
- `target_id`
- `target_uri`
- `label`
- `quote`
- `metadata_json`
- `created_at`

Constraints:

- At least one owner is required:
  `note_id IS NOT NULL OR discussion_message_id IS NOT NULL`.
- Paper and chat targets must resolve to existing local records.

### ExperimentRun

Structured experiment record scoped to a research project.

Fields:

- `id`
- `project_id`
- `title`
- `status`: `planned`, `running`, `completed`, `failed`, `archived`
- `hypothesis`
- `dataset`
- `code_ref`
- `command`
- `parameters_json`
- `metrics_json`
- `summary`
- `started_at`
- `completed_at`
- `created_at`
- `updated_at`

Constraints:

- Runs are archived by status, not hard-deleted through the UI.
- Metrics and parameters are stored as structured JSON so later discussion and
  search workflows can use them without parsing note prose.

### ExperimentArtifact

Reference to an artifact produced by an experiment run.

Fields:

- `id`
- `run_id`
- `artifact_type`: `metrics`, `checkpoint`, `figure`, `table`, `log`,
  `model`, `dataset`, `report`, `other`
- `uri`
- `label`
- `description`
- `metadata_json`
- `created_at`

## API Surface

### Paper APIs

- `POST /api/papers`
  - Input: arXiv URL, PDF URL, DOI, Semantic Scholar ID, or file upload token.
  - Output: paper ID and ingestion job ID.
- `POST /api/papers/upload`
  - Input: raw `application/pdf` request body.
  - Query: `filename` optional original filename, `title` optional display title.
  - Output: paper ID and ingestion status using the normal paper response shape.
- `GET /api/papers`
  - Query: search, tag, status, bookmarked, source, date range.
- `GET /api/papers/{paper_id}`
- `GET /api/papers/{paper_id}/chunks`
- `GET /api/papers/{paper_id}/fulltext`
- `GET /api/papers/{paper_id}/pages`
- `GET /api/papers/{paper_id}/pages/text`
- `GET /api/papers/{paper_id}/pages/{page_number}.png`
- `GET /api/papers/{paper_id}/pages/{page_number}/text`
- `POST /api/papers/{paper_id}/retry`
- `POST /api/papers/{paper_id}/bookmark`
- `POST /api/papers/{paper_id}/tags`

### Chat APIs

- `POST /api/chat/sessions`
- `GET /api/papers/{paper_id}/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `POST /api/chat/sessions/{session_id}/messages`
  - Supports streaming through server-sent events when requested.
- `POST /api/chat/messages`
  - Backward-compatible non-streaming message endpoint. If no selected passage
    or selected image region is supplied, Codex paper chat treats the whole
    paper file references and extracted full text as the active context.
- `GET /api/chat/messages/{message_id}/retrieval`
  - Returns chunks, graph paths, scores, and prompt metadata.

### Graph APIs

- `POST /api/papers/{paper_id}/literature-graph/build`
- `GET /api/papers/{paper_id}/literature-graph`
  - Query: `view=related|prior|derivative`
- `GET /api/literature/nodes/{node_id}`
- `POST /api/literature/import`

### Provider APIs

- `GET /api/providers`
- `POST /api/providers`
- `POST /api/providers/{provider_id}/healthcheck`
- `POST /api/providers/{provider_id}/set-default`
- `DELETE /api/providers/{provider_id}`

### Research Workspace APIs

- `POST /api/research/projects`
- `GET /api/research/projects`
- `GET /api/research/projects/{project_id}`
- `PATCH /api/research/projects/{project_id}`
- `GET /api/research/projects/{project_id}/export.md`
- `POST /api/research/questions`
- `GET /api/research/questions`
- `PATCH /api/research/questions/{question_id}`
- `POST /api/research/notes`
- `GET /api/research/notes`
- `GET /api/research/notes/{note_id}`
- `PATCH /api/research/notes/{note_id}`
- `POST /api/research/notes/{note_id}/links`
- `GET /api/research/notes/{note_id}/links`
- `POST /api/papers/{paper_id}/research-notes`
- `POST /api/chat/messages/{message_id}/research-note`

### Experiment APIs

- `POST /api/experiments/runs`
- `GET /api/experiments/runs`
- `GET /api/experiments/runs/{run_id}`
- `PATCH /api/experiments/runs/{run_id}`
- `POST /api/experiments/runs/{run_id}/research-note`
- `POST /api/experiments/runs/{run_id}/artifacts`
- `GET /api/experiments/runs/{run_id}/artifacts`

### GitHub APIs

- `GET /api/auth/github/start`
- `GET /api/auth/github/callback`
- `GET /api/github/repos`
- `POST /api/github/repo-links`

Copilot SDK, Codex, and MCP endpoints are post-MVP unless implementation
confirms official support and credentials in the target environment.

## Ingestion Pipeline

1. Normalize source identifier.
2. Fetch metadata from arXiv and optional Semantic Scholar.
3. Download PDF.
4. Convert PDF to Markdown.
5. Extract references and section structure.
6. Chunk Markdown.
7. Generate embeddings.
8. Extract entities.
9. Build single-paper graph.
10. Generate initial summary artifacts.
11. Mark paper ready.

Each step must be idempotent by content hash. A retry should resume from the
first missing or failed step.

## Retrieval Pipeline

Inputs:

- Paper ID.
- User query.
- Chat history.
- Selected passage or selected image region, when supplied.
- Whole-paper file references and extracted full text when no selection is supplied.
- Retrieval settings.

Steps:

1. Embed the user query.
2. Retrieve candidate chunks by vector similarity.
3. Extract query entities.
4. Match query entities to paper graph nodes.
5. Expand graph neighbors.
6. Rank candidates by combined vector, graph, section, recency, and query term
   signals.
7. Build cited context.
8. Generate response through selected provider.
9. Persist answer, citations, retrieval diagnostics, provider metadata, and
   latency.

## Literature Graph Algorithm

MVP algorithm:

1. Resolve seed paper to Semantic Scholar ID when possible.
2. Fetch seed metadata, references, and citations.
3. Create a candidate pool:
   - top references by influence and recency
   - top citations by influence and recency
   - papers sharing references with the seed
   - papers sharing citations with the seed
4. Score candidates:
   - direct citation edge: high directional score
   - bibliographic coupling: Jaccard overlap of references
   - co-citation: Jaccard overlap of citations
   - abstract embedding cosine similarity when available
   - year delta and citation count as tie-breakers
5. Classify:
   - Prior works: older papers cited by seed or central in shared references.
   - Derivative works: newer papers citing seed or central among later papers.
   - Related papers: high total score regardless of direction.
6. Store graph nodes and edges.
7. Return top `N` nodes, default 50.

Post-MVP:

- Add incremental graph expansion.
- Add community detection.
- Add graph snapshot comparison.
- Add local corpus influence scoring.
- Add explainable path ranking.

## Provider Adapter Contract

Generation adapter:

```text
generate(messages, model, tools, response_format, stream, metadata) -> GenerationResult
```

Embedding adapter:

```text
embed(texts, model, dimensions, metadata) -> EmbeddingResult
```

Agent adapter:

```text
run_task(task, context_refs, permissions, metadata) -> AgentRunResult
```

The OpenAI-compatible generation adapter must support:

- Responses API.
- Chat Completions API.
- Streaming where available.
- JSON or structured output when available.
- Timeout, retry, and rate-limit handling.

The agent adapter must not assume that Copilot or Codex credentials are
available. It must perform explicit health and capability checks.

## Security Requirements

- Store secrets server-side only.
- Redact API keys, bearer tokens, OAuth tokens, and signed URLs from logs.
- Do not send full PDFs to model providers unless the user explicitly enables
  that mode. Default is retrieved chunks only.
- Record which chunks were sent to external providers.
- Make provider calls opt-in per provider.
- OAuth tokens must be encrypted at rest or stored through an OS or deployment
  secret manager.
- Local single-user mode may skip full account management but must still protect
  provider secrets from the browser.

## Observability

Structured events:

- `paper_ingest_started`
- `paper_ingest_step_completed`
- `paper_ingest_failed`
- `provider_healthcheck_completed`
- `retrieval_started`
- `retrieval_completed`
- `generation_started`
- `generation_completed`
- `generation_failed`
- `literature_graph_build_started`
- `literature_graph_build_completed`
- `literature_graph_build_failed`

Every provider call log must include provider name, model, latency, status, and
token counts when available, but no secret values and no full prompt by default.

## Testing Requirements

MVP implementation should include:

- Unit tests for arXiv ID normalization.
- Unit tests for provider adapter request construction.
- Unit tests for chunk citation formatting.
- Unit tests for literature graph scoring.
- Integration test for paper ingestion with a small fixture PDF.
- Integration test for chat with a mocked OpenAI-compatible provider.
- Integration test for provider health check.
- Integration tests for research projects, notes, evidence links, paper-passage
  capture, Ask Paper answer capture, archival status updates, and Markdown
  project export.
- Integration tests for experiment runs, artifact references, experiment
  evidence links, run-to-note capture, and project export.
- End-to-end test for the main flow:
  - configure provider
  - ingest paper
  - ask question
  - view citations
  - build literature graph

## Known Constraints

- Connected Papers uses corpus-scale ranking. MVP will approximate this with
  API-backed candidate pools and local scoring.
- PDF conversion quality varies by paper layout.
- arXiv and Semantic Scholar rate limits can affect ingestion and graph builds.
- Copilot and Codex integrations have subscription and availability limits.
- Some OpenAI-compatible endpoints implement only Chat Completions, not
  Responses.
