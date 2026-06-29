# Open AlphaXiv

Open AlphaXiv is a local-first research paper workspace for reading arXiv
papers as selectable PDF pages, asking paper questions, and keeping notes in
one Docker-deployable app.

The app is designed for researchers who want a private paper reading surface:
paste an arXiv URL, read the imported PDF in the browser, highlight passages or
select page regions, and ask questions against the paper context.

## What You Can Do

- Import a paper from an arXiv URL.
- Read rendered PDF pages in a two-pane workspace with the assistant beside the
  reader.
- Highlight selectable PDF text and ask targeted questions about that passage.
- Select PDF page regions to include visual-region metadata in a question.
- Ask Codex questions against extracted paper text without exposing retrieval
  chunks in the reader.
- Render paper answers as Markdown, including headings, lists, tables, links,
  quotes, and code blocks.
- Manage a local Codex system prompt for answer language and output format.
- Create research projects, track research questions, and keep persistent
  Markdown notes beside the paper reader.
- Save highlighted paper passages and Ask Paper answers into research notes
  with evidence links.
- Track experiment runs with datasets, commands, code references, metrics,
  summaries, and artifact references.
- Record project-level research discussions and freeze grounding snapshots for
  later review.
- Search local research projects, notes, experiment runs, discussions, and
  snapshots from a compact research status dashboard.
- Export a research project as readable Markdown with paper and chat citations.
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

The API stores the paper metadata, downloads the PDF when available, extracts
text with Poppler, renders page images, creates a transparent page text layer
for highlighting, creates Markdown content, builds local retrieval data for
mock mode and graph construction, and makes the paper available in the reader.

The Docker images include `poppler-utils` for PDF text and page-image
extraction. When running the API directly on the host, install Poppler so
`pdftotext` and `pdftoppm` are available on `PATH`; otherwise Open AlphaXiv
falls back to metadata and abstract text.

## Local Codex Paper Q&A

Open AlphaXiv can answer paper questions with a local Codex agent. The backend
runs `codex exec` in read-only sandbox mode and sends paper metadata, selected
passage text, selected image-region metadata, and extracted paper text as prompt
context. The prompt uses a conservative size limit and adds a truncation marker
when a paper is too long for the local prompt budget.

The web UI also lets you set a local Codex system prompt for paper chat. This is
stored in browser local storage and sent only when Codex answer mode is used,
so you can control answer language, Markdown structure, JSON-only output, or
other response formatting instructions without changing backend environment
variables.

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
The Codex home mount is writable because the Codex CLI may update local session
state under `CODEX_HOME`; use a dedicated Codex home directory for this project
if you do not want the container to write to your primary `~/.codex` directory.

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

Run the web app against a non-default local API port:

```bash
cd web
VITE_API_URL=http://127.0.0.1:18000 npm run dev -- --host 127.0.0.1 --port 3310
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
