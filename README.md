# Open AlphaXiv

[English](README.md) | [繁體中文](README.zh-TW.md)

A local app for reading arXiv papers, asking questions about them, and
keeping notes. It runs on your machine and uses **your** coding-agent
logins or API keys.

It is not affiliated with [alphaXiv](https://www.alphaxiv.org/). The
app never calls `alphaxiv.org`.

## Features

- Import a paper from an arXiv URL, or upload a PDF
- Read pages in the browser, highlight text, and ask about a selection
- Answer with Claude Code, Codex, OpenCode, or any OpenAI-compatible
  endpoint — or use the built-in mock mode with no model
- Watch an arXiv category feed (metadata only until you open a paper)
- Related / prior / derivative papers from
  [Semantic Scholar](https://www.semanticscholar.org/)
- Notes, bookmarks, tags, research projects, and Markdown export
- [MCP](https://modelcontextprotocol.io/) tools so Cursor, Claude Code,
  or Codex can search and read your local library

Cached PDFs are for your own reading and research. Link back to the
[arXiv abstract page](https://arxiv.org/) for downloads. See
[NOTICE](NOTICE) and [Legal boundary](docs/LEGAL_BOUNDARY.md).

## Quick start

**Docker**

```bash
docker compose up --build
```

Then open http://127.0.0.1:3100 (API at http://127.0.0.1:8000).

```bash
WEB_PORT=3200 docker compose up -d
```

The compose stack uses SQLite. Claude Code and OpenCode stay on the
host; use the source install below if you want those as in-app
assistants.

**From source**

You need Python 3.10+, Node.js 20+, and
[Poppler](https://poppler.freedesktop.org/) (`pdftotext`, `pdftoppm`)
for full text and page images.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd web
npm install
npm run dev
```

Open http://127.0.0.1:3000. If that port is taken, run
`npm run dev -- --port 3310` and set
`OPEN_ALPHAXIV_CORS_ORIGIN=http://localhost:3310` on the API.

## Configuration

```bash
cp .env.example .env
```

| Variable | What it does |
| --- | --- |
| `OPEN_ALPHAXIV_CLAUDE_ENABLED=true` | Ask Paper through `claude` (already logged in on this machine) |
| `OPEN_ALPHAXIV_OPENCODE_ENABLED=true` | Ask Paper through `opencode` |
| `OPEN_ALPHAXIV_CODEX_ENABLED=true` | Ask Paper through `codex` |
| `SEMANTIC_SCHOLAR_API_KEY` | Literature graph. Without it, Semantic Scholar often returns HTTP 429 |
| `OPEN_ALPHAXIV_ARXIV_CATEGORIES` | Feed categories, default `cs.LG` |
| `OPENAI_COMPATIBLE_BASE_URL` | Optional HTTP API. Non-localhost hosts must use `https` |

The UI also has a provider form for OpenAI-compatible servers (including
Ollama on localhost). Keep keys on the server; they are not bundled into
the web app.

## MCP

Point a local agent at http://127.0.0.1:8000/mcp. Keep that port on
loopback.

**Cursor** (`mcp.json`):

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
```

Tools: `search_arxiv`, `ingest_paper`, `list_library`, `get_paper_text`,
`query_paper_pages`, `save_note`, `list_notes`.

## Tests

```bash
python3 -m pytest
cd web && npm run build
```

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
