# Research Survey: alphaXiv, Connected Papers, and alphaxiv-open

Survey date: 2026-06-28

## Objective

Survey the user-facing functions and implementation-relevant behavior of:

- alphaXiv
- Connected Papers
- `AsyncFuncAI/alphaxiv-open`

Then translate the findings into requirements for a local web application that
can run through Docker and connect to Codex, GitHub Copilot OAuth, or
OpenAI-compatible large language model APIs.

## Source Inventory

| Source | Evidence Used |
| --- | --- |
| alphaXiv | Public homepage at `https://www.alphaxiv.org/`, inspected 2026-06-28. |
| Connected Papers | Public homepage metadata at `https://www.connectedpapers.com/`, public bundled UI text from `https://www.connectedpapers.com/assets/index-DcBynCAl.js`, inspected 2026-06-28. |
| alphaxiv-open | GitHub repository and raw files at `https://github.com/AsyncFuncAI/alphaxiv-open`, inspected 2026-06-28. |
| GitHub Copilot and Codex | GitHub Docs for Copilot, Copilot SDK, BYOK, MCP, and OpenAI Codex, inspected 2026-06-28. |
| OpenAI API | OpenAI API documentation for Responses and embeddings, inspected 2026-06-28. |

Detailed source links:

- alphaXiv homepage: `https://www.alphaxiv.org/`
- alphaXiv paper page sample: `https://www.alphaxiv.org/abs/2606.25996`
- Connected Papers homepage: `https://www.connectedpapers.com/`
- Connected Papers UI bundle inspected for public product text:
  `https://www.connectedpapers.com/assets/index-DcBynCAl.js`
- alphaxiv-open repository: `https://github.com/AsyncFuncAI/alphaxiv-open`
- alphaxiv-open README:
  `https://raw.githubusercontent.com/AsyncFuncAI/alphaxiv-open/main/README.md`
- alphaxiv-open Docker Compose:
  `https://raw.githubusercontent.com/AsyncFuncAI/alphaxiv-open/main/docker-compose.yml`
- alphaxiv-open environment example:
  `https://raw.githubusercontent.com/AsyncFuncAI/alphaxiv-open/main/.env.example`
- GitHub Copilot MCP documentation:
  `https://docs.github.com/en/copilot/concepts/context/mcp`
- GitHub Copilot SDK GitHub OAuth documentation:
  `https://docs.github.com/en/copilot/how-tos/copilot-sdk/setup/github-oauth`
- GitHub Copilot SDK authentication documentation:
  `https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/authenticate`
- GitHub Copilot SDK BYOK documentation:
  `https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/byok`
- GitHub Copilot app BYOK model provider documentation:
  `https://docs.github.com/en/copilot/how-tos/github-copilot-app/use-byok-models`
- GitHub OpenAI Codex integration documentation:
  `https://docs.github.com/en/copilot/concepts/agents/openai-codex`
- OpenAI Responses API reference:
  `https://platform.openai.com/docs/api-reference/responses`
- OpenAI embeddings guide:
  `https://developers.openai.com/api/docs/guides/embeddings`
- OpenAI Codex manual sections on ChatGPT sign-in, access tokens, SDK,
  and app server, generated from official OpenAI documentation on
  2026-06-28.

## alphaXiv Functional Survey

Observed public features:

- Explore feed with recently added research items.
- Search box labeled "Ask or search anything..." with smart search and style
  controls.
- Paper pages expose a `Paper` view with adjacent `Assistant`, `My Notes`,
  `Comments`, and `Similar` tool surfaces.
- Paper cards with title, date, authors, short generated summary, tags,
  counts, bookmark action, audio action, and related GitHub links when present.
- "View blog" action on paper cards, implying a generated or curated article
  view in addition to raw paper metadata.
- Authentication entry point and Pro upsell.
- Personalized feed callout.
- Researcher directory entry point.
- Conference/event surfaces, including an ICML 2026 navigation item and event
  listings.
- Browser extension link.
- Dark mode.

Product interpretation:

- alphaXiv is not just a PDF chat interface. It combines discovery, feed
  personalization, summaries, audio, bookmarking, topic tags, and blog-like
  explanations.
- The MVP should focus on local paper ingestion, search, paper detail, chat,
  generated summaries, bookmarks, and graph-based related-paper discovery.
- The paper detail screen should prioritize a reader-first layout: source
  paper on the left, assistant and paper tools on the right. Selected text from
  the reader should become explicit chat context so cited answers can focus on
  the passage the user is reading.
- Audio, public profiles, Pro billing, event programming, and browser extension
  support should be post-MVP unless explicitly prioritized.

## Connected Papers Functional Survey

Observed public features:

- The product describes itself as a visual tool for finding and exploring
  academic papers relevant to a field of work.
- Landing flow asks the user to enter a paper identifier, then "Build a graph".
- The graph view is centered around an origin paper.
- Public UI text says each graph analyzes roughly 50,000 papers and selects a
  few dozen with the strongest connections to the origin paper.
- Papers are arranged by similarity, not merely by direct citation edges.
- The similarity metric is based on co-citation and bibliographic coupling.
- A force-directed graph is used to cluster similar papers and push less similar
  papers apart.
- Selecting a node highlights the shortest path from that node to the origin
  paper in similarity space.
- Prior Works view surfaces important ancestor works.
- Derivative Works view surfaces literature reviews and later state-of-the-art
  papers that followed the input paper.
- The product uses the Semantic Scholar Paper Corpus.

Product interpretation:

- Connected Papers is primarily a literature graph exploration system, not a
  document question-answering system.
- The local product should separate two graphs:
  - Paper knowledge graph inside one PDF for question answering.
  - Literature graph across papers for discovery.
- The MVP can approximate the Connected Papers behavior with Semantic Scholar
  metadata, references, citations, co-citation, bibliographic coupling, and a
  force-directed graph layout. Full corpus-scale ranking is a roadmap item.

## alphaxiv-open Functional and Architecture Survey

Confirmed from the repository README:

- Backend: FastAPI.
- PDF conversion: Microsoft Markitdown.
- Retrieval/indexing: MiniRAG, distributed as LightRAG.
- Chat generation: Google Gemini API.
- Embeddings: OpenAI embeddings.
- Main paper processing flow:
  - User submits an arXiv URL.
  - System downloads the PDF from arXiv.
  - PDF is converted to Markdown.
  - Markdown is cleaned and chunked.
  - MiniRAG extracts entities and creates embeddings.
  - MiniRAG builds entity nodes, text chunk nodes, entity-to-entity edges, and
    entity-to-chunk edges.
  - Edge descriptions are generated to form a semantic-aware heterogeneous
    graph.
- Main question-answering flow:
  - User asks a question.
  - System extracts entities from the query.
  - System predicts potential answer types.
  - Query is mapped to graph entities.
  - Retrieval uses graph traversal and ranks reasoning paths.
  - Retrieved chunks are sent to Gemini for response generation.
- API endpoints documented:
  - `POST /api/papers/process`
  - `POST /api/chat`
- Docker Compose reference has three services:
  - `lightrag` on port 9721
  - `api` on port 8000
  - `frontend` on port 3000
- Environment variables include:
  - `GOOGLE_API_KEY`
  - `OPENAI_API_KEY`
  - `GEMINI_MODEL`
  - MiniRAG host, port, chunk size, overlap, embedding dimensions, threshold,
    top-k, binding, and embedding model.

Implementation interpretation:

- The reference is a strong baseline for paper chat, but it is not sufficient
  for the full requested product because it lacks a Connected Papers-style
  cross-paper literature graph and provider-neutral agent/model routing.
- The local implementation should preserve the useful pipeline shape while
  replacing hard-coded Gemini generation with a model provider abstraction.
- The local implementation should support a simple retrieval fallback when graph
  indexing is unavailable, but MVP success should require graph-backed
  retrieval for processed papers.

## Model and Agent Integration Survey

OpenAI API:

- The Responses API is the current primary interface for generating model
  responses and supports text, image, structured outputs, conversation state,
  tools, function calling, and streaming.
- OpenAI embeddings return vector arrays that can be saved in a vector database.
  `text-embedding-3-small` defaults to 1536 dimensions.

GitHub Copilot:

- GitHub Copilot supports MCP as a way to extend Copilot with external tools and
  data sources.
- The GitHub MCP server can invoke GitHub tools, including Copilot cloud agent
  where subscription requirements are met.
- Copilot SDK authentication supports GitHub OAuth device flow for signed-in
  users in interactive CLI scenarios.
- Copilot SDK BYOK supports OpenAI, Azure OpenAI, Anthropic, Ollama, Microsoft
  Foundry Local, and other OpenAI-compatible endpoints. BYOK uses static
  credentials and does not count against Copilot premium request quotas.
- The GitHub Copilot app can use "any OpenAI-compatible HTTP endpoint" as a
  model provider when configured by the user.

OpenAI Codex through GitHub Copilot:

- GitHub documents OpenAI Codex as a public preview integration powered by
  Copilot.
- The OpenAI Codex coding agent is available for paid Copilot plans.
- "Sign in with Copilot" in the OpenAI Codex VS Code extension is limited to
  GitHub Copilot Pro+ and Copilot Max subscribers.

OpenAI Codex official authentication boundary:

- Codex supports ChatGPT sign-in and API-key login for Codex surfaces such as
  the web product, CLI, IDE extension, SDK, and app server.
- Browser sign-in for Codex returns credentials to Codex clients. It is not a
  documented third-party browser OAuth flow that another local web app can use
  as a generic LLM provider credential.
- Enterprise and Business environments can create Codex access tokens for
  trusted automation. These tokens are scoped to Codex permissions and should
  not be treated as ordinary OpenAI API keys.
- The Codex SDK and app server are appropriate for optional local agent
  automation around software-development tasks. They are not the default model
  call path for paper question answering.
- Codex non-interactive mode (`codex exec`) can be used for local, scripted
  agent tasks. It prints the final answer to stdout, can run with
  `--ephemeral`, and supports explicit sandbox and approval settings.

Product boundary:

- MVP must not promise unrestricted access to Copilot or Codex as generic model
  APIs. The safe contract is:
  - Support OpenAI-compatible chat and embedding APIs directly.
  - Support GitHub OAuth only for features that GitHub officially allows, such
    as user identity, repository access, and optional Copilot SDK or MCP flows.
  - Treat Codex and Copilot agent execution as optional connectors with explicit
    subscription, environment, and user-authentication requirements.
  - Expose Codex local connector status separately from model-provider health so
    users can distinguish "Codex CLI authenticated" from "paper chat model
    provider configured."
  - Allow paper chat to use Codex only through an explicit local-agent mode that
    calls `codex exec` from the backend with read-only sandboxing. This mode
    must remain opt-in because it starts an agent process from an HTTP request.

## Requirements Derived From Survey

MVP must include:

- Local web UI.
- Docker Compose deployment.
- arXiv URL ingestion.
- alphaXiv-like paper reader with paper content on the left and assistant tools
  on the right.
- Selection-aware paper chat that includes highlighted reader text in retrieval
  metadata and the answer focus.
- Optional Codex answer mode for paper chat, using retrieved chunks as the
  bounded context passed to the local Codex agent.
- PDF download, conversion, cleanup, chunking, and metadata extraction.
- Graph-backed paper question answering.
- OpenAI-compatible LLM provider configuration.
- Embedding provider configuration.
- Paper library with search, tags, bookmarks, processing status, and generated
  summaries.
- Literature graph from a seed paper with prior works, derivative works, and
  related papers.
- Source-grounded answers with citations to paper sections or chunks.
- Durable storage for papers, chunks, embeddings, graph edges, chat sessions,
  and provider settings.

MVP should include:

- Semantic Scholar metadata connector.
- Basic RSS or arXiv category ingestion for feed-like discovery.
- Exportable notes.
- Provider health checks.

Post-MVP should include:

- Audio summaries.
- Browser extension.
- User profiles and public sharing.
- Multi-paper synthesis notebooks.
- Advanced personalized feed.
- GitHub Copilot SDK and Codex agent task execution, if the user has the
  required plan and local credentials.
