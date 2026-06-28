# Open AlphaXiv

Open AlphaXiv is a local-first research paper workspace for reading arXiv
papers, importing paper metadata, asking cited questions, and keeping notes in
one Docker-deployable app.

The app is designed for researchers who want a private paper reading surface:
paste an arXiv URL, read the imported paper in the browser, select passages, and
ask questions against the paper context. Answers include chunk citations so the
reader can move from summary back to source text.

## What You Can Do

- Import a paper from an arXiv URL.
- Read the paper in a two-pane workspace with the assistant beside the reader.
- Select text from the paper and ask targeted questions about that passage.
- Ask cited questions against retrieved paper chunks.
- Use the built-in mock answer mode for local development without an external
  model.
- Use local Codex through `codex exec` for paper Q&A when the host machine is
  already logged in to the Codex CLI.
- Bookmark, tag, and export paper notes as Markdown.
- Explore related, prior, and derivative literature graph views.

## Run Locally

Run the full Docker stack:

```bash
docker compose up --build
```

Open the app:

```text
http://127.0.0.1:3100
```

Default local endpoints:

- Web: `http://127.0.0.1:3100`
- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

Use a different web port when 3100 is already occupied:

```bash
WEB_PORT=3200 docker compose up -d web
```

## Paper Import

Paste an arXiv paper URL into the import field, for example:

```text
https://arxiv.org/abs/1706.03762
```

The API stores the paper metadata, creates Markdown content, chunks the text,
builds local retrieval data, and makes the paper available in the reader.

## Local Codex Paper Q&A

Open AlphaXiv can answer paper questions with a local Codex agent. The backend
runs `codex exec` in read-only sandbox mode and sends only the selected passage
plus retrieved paper chunks as prompt context.

Codex login is handled by the host CLI, not by the web UI:

```bash
codex login
OPEN_ALPHAXIV_CODEX_ENABLED=true python -m uvicorn app.main:app --reload
```

For Docker, mount the host Codex CLI and credentials into the API container:

```bash
bash scripts/check-codex-docker.sh
```

The script prints the exact environment variables and compose command for the
current machine. The generated command uses `docker-compose.codex.yml`, which
mounts:

- the host Node prefix containing `bin/codex` at `/opt/codex-node`
- the host Codex credential directory at `/codex-home`
- `CODEX_HOME=/codex-home`
- `OPEN_ALPHAXIV_CODEX_ENABLED=true`

If the host Codex install uses file-based authentication, `auth.json` is mounted
into the container. Treat that file as a password. The web UI displays Codex
availability and setup commands, but it does not start or proxy `codex login`.

Relevant Codex settings:

- `OPEN_ALPHAXIV_CODEX_ENABLED=true`
- `OPEN_ALPHAXIV_CODEX_CLI_PATH=codex`
- `OPEN_ALPHAXIV_CODEX_MODEL=` optional model override
- `OPEN_ALPHAXIV_CODEX_TIMEOUT_SECONDS=180`
- `OPEN_ALPHAXIV_CODEX_SANDBOX=read-only`
- `CODEX_HOME`, `CODEX_ACCESS_TOKEN`, `CODEX_API_KEY`, or
  `CODEX_AUTH_JSON_PATH` when required by the backend runtime
- `OPEN_ALPHAXIV_HOST_NODE_PREFIX` and `OPEN_ALPHAXIV_HOST_CODEX_HOME` when
  using `docker-compose.codex.yml`

## Development Checks

Run backend tests:

```bash
env PYTHONPATH=.:.deps python3 -m pytest
```

Build the web app:

```bash
cd web
npm install
npm run build
```

Check the Codex Docker mount setup:

```bash
bash scripts/check-codex-docker.sh
```

## Project Docs

- [Product requirements](docs/PRD.md)
- [Technical specification](docs/SPEC.md)
- [Research survey](docs/research-survey.md)
- [MVP and roadmap](docs/MVP_ROADMAP.md)
