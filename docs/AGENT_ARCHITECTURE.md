# Agent and Model Integration Architecture

Survey date: 2026-08-17

## Decision

Three stacked runtimes, in this order:

1. **MCP server** (primary way to spend coding-agent subscriptions)
2. **Official CLI spawn** (in-app Ask Paper using Codex / Claude Code / OpenCode binaries)
3. **OpenAI-compatible HTTP** (API keys, Ollama, vLLM, LiteLLM)

Do not add a fourth runtime that replays vendor web cookies.

## Why this order

Large coding-agent products do not expose a generic "run my Cursor subscription
from your SaaS" HTTP API that you call with a cookie. They expose MCP, and
some also document a first-party CLI or SDK.

Evidence:

- alphaXiv's own agent surface is MCP at `https://api.alphaxiv.org/mcp/v1`,
  with setup snippets for Claude Code, Codex CLI, Cursor, and VS Code
  (`https://www.alphaxiv.org/docs/mcp`, fetched 2026-08-17).
- Claude Code documents MCP as the way to attach external tools
  (`https://code.claude.com/docs/en/mcp`).
- Codex CLI documents MCP in `~/.codex/config.toml` and `codex mcp add`
  (`https://developers.openai.com/codex/mcp`).
- Cursor documents MCP via `mcp.json` (`https://cursor.com/docs/mcp`).
- Cursor also documents a headless CLI `agent -p` (`https://cursor.com/docs/cli/headless`,
  fetched 2026-08-17) and a TypeScript SDK `@cursor/sdk` with `CURSOR_API_KEY`
  (`https://cursor.com/docs/sdk/typescript`, fetched 2026-08-17).
- GitHub documents Copilot SDK auth for third-party apps, including OAuth
  GitHub Apps that pass a user token (`https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/authenticate`,
  fetched 2026-08-17).
- OpenCode documents `opencode run` plus provider `/connect`
  (`https://opencode.ai/docs/cli/`, `https://opencode.ai/docs/providers/`).

MCP remains the default join point for Cursor in this product. An in-app
`agent -p` or `@cursor/sdk` adapter is optional later, with the user's own
`CURSOR_API_KEY` or `agent login`. Do not scrape the Electron app.

## Runtime 1: MCP server (subscription-safe)

This app becomes a tool provider. The user keeps using Claude Code, Codex,
Cursor, or Copilot as the agent. Those clients already hold the subscription.

Transport: Streamable HTTP on the local API, plus a stdio launcher for
clients that prefer a child process.

Initial tool set (independent names; do not copy alphaXiv proprietary
report formats):

| Tool | Behavior |
| --- | --- |
| `search_arxiv` | Query the arXiv API. Return metadata and landing URLs. |
| `ingest_paper` | Import an arXiv id or local PDF into the library. |
| `list_library` | List local papers, tags, bookmarks, folders. |
| `get_paper_text` | Return extracted text already stored locally. |
| `query_paper_pages` | Return page-bounded excerpts for a list of questions. |
| `save_note` | Write a research note with optional passage quote. |
| `list_notes` | Search notes in a project. |

Quota: MCP tool calls do not consume a second model bill inside this app.
The agent client bills the user's existing subscription.

Auth: bind MCP to localhost and the same local session as the web UI. Do not
expose the MCP port on the public internet in v1.

## Runtime 2: Official CLI spawn (in-app assistant)

Used when the user asks a question inside this web UI and wants the answer
from a coding agent they already logged into on the host.

| Adapter | Binary | Documented non-interactive entry | Credential |
| --- | --- | --- | --- |
| Codex | `codex` | Phase 1: `codex exec --ephemeral --sandbox read-only --skip-git-repo-check`. Phase 1b: `codex app-server` for streamed in-app UI (`https://developers.openai.com/codex/app-server`, "deep integration inside your own product"). OpenClaw uses ChatGPT OAuth plus this harness (`https://docs.openclaw.ai/concepts/oauth`). This repo spawns the official binary; it does not reimplement `auth.openai.com`. | Host `codex login` or `CODEX_API_KEY` (`https://developers.openai.com/codex/noninteractive`) |
| Claude Code | `claude` | `claude -p --output-format text` with the prompt on stdin, without `--bare`, so the official CLI can use its own login. Do not pass empty `--allowedTools`: Claude Code 2.1 treats that flag as variadic and consumes the prompt (`https://code.claude.com/docs/en/headless`). | Official Claude Code login on that machine. `--bare` requires `ANTHROPIC_API_KEY` and must not be the subscription path. |
| OpenCode | `opencode` | `opencode run --format default --dir <cwd>`. `--dir` is required; subprocess `cwd=` alone yields empty stdout on OpenCode 1.14.50. | OpenCode `/connect` for ChatGPT Plus, GitHub Copilot, API keys (`https://opencode.ai/docs/providers/`) |
| Cursor | `agent` | Optional later: `agent -p` (`https://cursor.com/docs/cli/headless`). Not a Phase 1 adapter. MCP remains the default. | `CURSOR_API_KEY` or `agent login` |
| Gemini CLI | `gemini` | vendor `-p` / non-interactive flag, added only after a capability probe | Gemini CLI login or API key |

Shared contract:

```text
run_task(prompt: str, cwd: Path, timeout_s: int, extra_args: list[str]) -> AgentRunResult
```

`AgentRunResult` fields: `ok`, `stdout`, `stderr_preview`, `adapter`,
`binary_path`, `latency_ms`, `exit_code`.

Constraints copied from the current Codex path in
`app/services.py:2529-2583`:

- Isolated temp working directory unless a test supplies `cwd`.
- Read-only sandbox when the binary supports it.
- No file edits, no shell, no web browsing in the paper-Q&A system prompt.
- Truncation marker when paper text exceeds the prompt budget.
- Capability probe before the UI offers the adapter.
- Secrets never returned to the browser.

Claude Code extra constraint: do not pass extracted OAuth tokens into
environment variables. Do not call the Claude Agent SDK with a Pro/Max
OAuth token. Anthropic's legal page states OAuth is for native Anthropic
apps and that third-party products must use Console API keys
(`https://code.claude.com/docs/en/legal-and-compliance`). Spawning the
official `claude` binary on the operator's machine is the only
subscription-adjacent in-app path this project will ship. High-frequency
automated wrapping may still fall outside "ordinary, individual usage";
keep paper Q&A interactive and rate-limited.

OpenCode extra constraint: do not enable plugins that OpenCode itself
marks as prohibited for Claude Pro/Max OAuth
(`https://opencode.ai/docs/providers/`). ChatGPT Plus and GitHub Copilot
through OpenCode's documented `/connect` remain in scope.

## Runtime 3: OpenAI-compatible HTTP (API keys)

Used for:

- streaming paper chat without spawning an agent process
- embeddings for retrieval
- mock mode in tests

Wire APIs: Chat Completions first, Responses second. Health check must perform a real HTTP call for
`provider_type=openai_compatible` (`app/agents/openai_compatible.py`).

Supported endpoints: OpenAI, compatible proxies, Ollama, LM Studio, vLLM,
LiteLLM. Secrets stay in the server store, redacted in list responses
(`redact_provider` already exists in `app/services.py:2768`).

## Anti-patterns

| Pattern | Status |
| --- | --- |
| Cookie / `auth.json` replay into a custom HTTP client | Forbidden |
| Unofficial alphaxiv.org API clients | Forbidden |
| Scraping the Cursor IDE or replaying cursor.com cookies | Forbidden |
| In-app Cursor CLI/SDK without the user's `CURSOR_API_KEY` or `agent login` | Unsupported |
| Claude Agent SDK + Pro/Max OAuth | Forbidden by Anthropic docs |
| Treating mock hash embeddings as production retrieval | Current code; replace in Phase 2 |

## Current repository state

Implemented on `feature/phase1-agent-runtime` (2026-08-17):

- Codex, Claude Code CLI, OpenCode, and OpenAI-compatible HTTP adapters
  under `app/agents/`
- `GET /api/agents/status` and Ask Paper modes
  `mock | codex | claude_cli | opencode | openai_compatible`
- Localhost MCP JSON-RPC at `POST /mcp` and `python -m app.mcp`
- Provider healthcheck that calls `{base_url}/models` for
  `openai_compatible` rows
- MCP tools `query_paper_pages` and `list_notes` (2026-08-17/18)
- Semantic Scholar literature graph with attribution (Phase 2)

Missing:

- Cursor `agent -p` / `@cursor/sdk` in-app adapter (MCP covers Cursor)
- Copilot SDK in-process adapter (MCP covers Copilot Chat)
- Streaming chat

## Capability matrix (target)

| Client | How the user spends the subscription | What this app provides |
| --- | --- | --- |
| Cursor | Cursor Agent + MCP; optional later `agent -p` or `@cursor/sdk` | Local paper tools |
| Claude Code | Claude Code session or `claude -p` | MCP + optional CLI spawn |
| Codex | Codex TUI/IDE or `codex exec` | MCP + existing CLI spawn |
| OpenCode | `opencode run` / TUI | MCP + CLI spawn |
| Copilot | Copilot Chat MCP / documented SDK | MCP first; SDK later |
| Raw API | User-supplied key | OpenAI-compatible adapter |
