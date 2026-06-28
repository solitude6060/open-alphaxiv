# Open AlphaXiv Planning Workspace

This repository contains MVP1 of a local, Docker-deployable research paper
exploration application inspired by alphaXiv, Connected Papers, and the
`AsyncFuncAI/alphaxiv-open` reference implementation.

## MVP1 Status

MVP1 implements the first usable local workflow:

1. Configure and health-check a local mock OpenAI-compatible provider.
2. Ingest an arXiv paper URL.
3. Convert the paper metadata into Markdown, chunks, embeddings, and graph data.
4. Ask cited questions against retrieved paper chunks.
5. Build related, prior, and derivative literature graph views.
6. Bookmark, tag, and export paper notes as Markdown.

The backend uses SQLite for MVP1 application state while Docker Compose still
starts Postgres and Redis so the service topology matches the planned
deployment shape. Moving persistence and jobs fully onto Postgres and Redis is
the next implementation step.

## Run Locally

```bash
python3 -m pytest tests
cd web && npm install && npm run build
```

Run the full Docker stack:

```bash
docker compose up --build
```

The web service is exposed on port 3100 by default:

```bash
http://localhost:3100
```

Override the external web port when needed:

```bash
WEB_PORT=3200 docker compose up -d web
```

Default URLs:

- Web: `http://localhost:3100` or the configured `WEB_PORT`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

## Planning Documents

- [Research survey](docs/research-survey.md)
- [Product requirements document](docs/PRD.md)
- [Technical specification](docs/SPEC.md)
- [MVP and roadmap](docs/MVP_ROADMAP.md)
