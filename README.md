# Open AlphaXiv

Local-first paper workspace: discover arXiv work, read the PDF, ask grounded
questions with your own coding-agent logins or APIs, keep notes, and inspect
related literature.

This is an independent local product, not an official alphaXiv service. It
does not call `alphaxiv.org` or `api.alphaxiv.org`. See
[Legal boundary](docs/LEGAL_BOUNDARY.md) and [NOTICE](NOTICE).

Living documents: [canonical index](docs/CANONICAL.md). Historical 2026-06
files (`docs/SPEC.md`, `docs/PRD.md`, `docs/MVP_ROADMAP.md`) are archives.

## What works today

- Import an arXiv URL or a local PDF. Metadata always keeps an `arxiv.org`
  landing URL. Cached PDFs are for the operator's personal or research use.
- Read page images with a selectable text layer. Highlight a passage or a
  page region and ask about that selection.
- Ask Paper in `mock`, `codex`, `claude_cli`, `opencode`, or
  `openai_compatible` mode. Mock needs no model. The other modes stay off
  until you set the matching enable flag.
- Refresh a local arXiv category feed (default `cs.LG`). Feed rows are
  metadata only until you ingest a paper.
- Build a literature graph from Semantic Scholar. The Similar panel stays
  empty until a successful build. Failed calls do not invent placeholder
  papers. Attribute the data to Semantic Scholar.
- Research projects, notes, experiment runs, discussions, bookmarks, tags,
  and Markdown export.
- Localhost MCP so Cursor, Claude Code, or Codex can search and read the
  library without a second model bill inside this app.

## What this is not

- A public clone of alphaxiv.org (no comments network, events, or Pro
  billing).
- A public PDF host. Do not expose the API on the internet and serve
  cached e-prints to other people.
- An in-app Cursor or Claude Pro OAuth wrapper. Cursor joins through MCP.
  Claude subscription answers use the official `claude` binary, not
  `--bare`.

The private folder name may keep `alphaxiv`. Choose a different public
name before marketing. The prefix `open-` does not make that mark safe.

## Requirements

- Python 3.10+ with `pip install -r requirements.txt`
- Node.js 20+ for `web/`
- Poppler (`pdftotext`, `pdftoppm`) for full text and page images. Without
  it, ingest falls back to metadata and the abstract.
- Optional: host `codex`, `claude`, and `opencode` on `PATH` for in-app
  answers. Those binaries must already be logged in on this machine.

## Run on the host

This is the path that can use Claude Code and OpenCode. Copy
`.env.example` to `.env` and edit flags there, or export them in the
shell.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPEN_ALPHAXIV_CLAUDE_ENABLED=true
export OPEN_ALPHAXIV_OPENCODE_ENABLED=true
export OPEN_ALPHAXIV_CORS_ORIGIN=http://localhost:3000
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. API docs: `http://127.0.0.1:8000/docs`.

If this machine already has dependencies under `.deps` (gitignored):

```bash
export PYTHONPATH=.:.deps
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If port 3000 is taken:

```bash
cd web
npm run dev -- --host 127.0.0.1 --port 3310
```

Set `OPEN_ALPHAXIV_CORS_ORIGIN=http://localhost:3310` on the API.

## Run with Docker

```bash
docker compose up --build
```

- Web: `http://127.0.0.1:3100`
- API: `http://127.0.0.1:8000`

Compose starts `api`, `web`, and a stub `worker`. It uses SQLite on the
`app-data` volume. It does not start Postgres or Redis.

```bash
WEB_PORT=3200 docker compose up -d web
```

The image has Poppler. It does not include your Claude or OpenCode logins.
Compose forwards Codex flags only. For Claude or OpenCode Ask Paper, run
the API on the host.

To mount a host Codex CLI into the API container:

```bash
bash scripts/check-codex-docker.sh
```

Treat a mounted `auth.json` as a password. Prefer a dedicated
`CODEX_HOME` if you do not want the container to write to `~/.codex`.

## Ask Paper

Pick the mode in the reader. Modes other than mock stay disabled until the
backend probe reports them available.

| Mode | How it runs | Enable |
| --- | --- | --- |
| `mock` | Extractive local answer | always on |
| `claude_cli` | `claude -p` with the prompt on stdin, no `--bare` | `OPEN_ALPHAXIV_CLAUDE_ENABLED=true` |
| `opencode` | `opencode run --format default --dir <cwd>` | `OPEN_ALPHAXIV_OPENCODE_ENABLED=true` |
| `codex` | `codex exec --ephemeral --sandbox read-only` | `OPEN_ALPHAXIV_CODEX_ENABLED=true` |
| `openai_compatible` | `POST {base_url}/chat/completions` | create a provider and pass healthcheck |

Logins stay in the official CLIs. This app does not copy OAuth tokens out
of `~/.claude`, `~/.codex`, or the browser.

The optional system prompt in the UI is stored in browser local storage
and sent only with non-mock modes.

Research Discussions can also call Codex with a frozen project snapshot.

## Feed and literature graph

Refresh the library feed to pull the latest metadata for
`OPEN_ALPHAXIV_ARXIV_CATEGORIES` (default `cs.LG`). The client waits at
least `OPEN_ALPHAXIV_FEED_MIN_INTERVAL_SECONDS` (default 900) between
refreshes unless you force one. Opening a card is what fetches the PDF.

The Similar panel does not auto-build on ingest. Click build after you
have a `SEMANTIC_SCHOLAR_API_KEY` if unauthenticated requests return
HTTP 429. Graph v1 uses direct citations and cited-by edges only.

## MCP (localhost)

Bind the API to loopback. Do not publish `/mcp` on the public internet.

Cursor `mcp.json`:

```json
{
  "mcpServers": {
    "open-alphaxiv": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

```bash
claude mcp add --transport http open-alphaxiv http://127.0.0.1:8000/mcp
codex mcp add open-alphaxiv --url http://127.0.0.1:8000/mcp
python -m app.mcp
```

Tools: `search_arxiv`, `ingest_paper`, `list_library`, `get_paper_text`,
`query_paper_pages`, `save_note`, `list_notes`. `search_arxiv` only calls
`export.arxiv.org` and shares the 3-second arXiv limiter.

## Environment

Copy `.env.example` to `.env`. `.env` is gitignored.

| Variable | Role |
| --- | --- |
| `OPEN_ALPHAXIV_STORAGE_DIR` | Paper files and SQLite parent (default `./data`) |
| `OPEN_ALPHAXIV_DATABASE_PATH` | SQLite path |
| `OPEN_ALPHAXIV_CORS_ORIGIN` | Browser origin allowed to call the API |
| `OPEN_ALPHAXIV_CLAUDE_ENABLED` | Spawn `claude -p` |
| `OPEN_ALPHAXIV_OPENCODE_ENABLED` | Spawn `opencode run` |
| `OPEN_ALPHAXIV_CODEX_ENABLED` | Spawn `codex exec` |
| `OPEN_ALPHAXIV_ARXIV_CATEGORIES` | Feed categories, comma-separated |
| `SEMANTIC_SCHOLAR_API_KEY` | Reliable literature-graph builds |
| `OPENAI_COMPATIBLE_BASE_URL` | Optional HTTP provider. Non-localhost hosts must be `https`. |

Do not put API keys in the frontend bundle. `CODEX_ACCESS_TOKEN` and
`CODEX_API_KEY` are optional overrides; prefer the host CLI login.

## Tests

```bash
env PYTHONPATH=.:.deps python3 -m pytest
# or, with a venv:
python3 -m pytest
```

```bash
cd web
npm run build
```

```bash
docker compose config -q
```

Live checks (network, operator accounts):

```bash
env PYTHONPATH=.:.deps python3 scripts/live_phase2_check.py
env PYTHONPATH=.:.deps OPEN_ALPHAXIV_CLAUDE_ENABLED=true OPEN_ALPHAXIV_OPENCODE_ENABLED=true python3 scripts/live_phase1_qa.py
```

## Docs and license

- [Canonical index](docs/CANONICAL.md)
- [Product contract](docs/PRODUCT_CONTRACT.md)
- [Legal boundary](docs/LEGAL_BOUNDARY.md)
- [Agent architecture](docs/AGENT_ARCHITECTURE.md)
- [Recreation plan](docs/ALPHAXIV_RECREATION_PLAN.md)

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
