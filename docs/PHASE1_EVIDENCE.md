# Phase 1 evidence

Recorded: 2026-08-17 on this machine.
Branch: `feature/phase1-agent-runtime`.

This file contains command output from this session. It does not contain
API keys or auth files.

## Automated tests

Command:

```bash
env PYTHONPATH=.:.deps python3 -m pytest tests/test_agents.py tests/test_mcp.py tests/test_api.py tests/test_services.py -q
```

Result: 76 passed, exit code 0.

Focused rerun in this evidence pass:

```text
14 passed in 0.66s
pytest_exit:0
```

## Host binaries

```text
/home/ma/.nvm/versions/node/v22.23.1/bin/codex
codex_exit:0
/home/ma/.local/bin/claude
claude_exit:0
/home/ma/.local/bin/opencode
opencode_exit:0
```

Versions:

```text
codex-cli 0.147.0
codex_version_exit:0
2.1.233 (Claude Code)
claude_version_exit:0
1.14.50
opencode_version_exit:0
```

## Adapter status without enable flags

In-process `collect_agent_status` with empty providers and Codex disabled:

```text
codex: available=False reason=Set OPEN_ALPHAXIV_CODEX_ENABLED=true to use Codex paper chat.
claude_cli: available=False reason=Set OPEN_ALPHAXIV_CLAUDE_ENABLED=true to use Claude Code paper chat.
opencode: available=False reason=Set OPEN_ALPHAXIV_OPENCODE_ENABLED=true to use OpenCode paper chat.
openai_compatible: available=False reason=Create an openai_compatible provider with a base_url, then run healthcheck.
status_exit:0
```

Binaries are present. Paper chat adapters stay unavailable until the matching
`OPEN_ALPHAXIV_*_ENABLED` flag or a healthy HTTP provider is configured.

## Adapter status with enable flags (no paper Q&A)

Command (2026-08-18): `OPEN_ALPHAXIV_CODEX_ENABLED=true`,
`OPEN_ALPHAXIV_CLAUDE_ENABLED=true`, `OPEN_ALPHAXIV_OPENCODE_ENABLED=true`,
then `collect_agent_status` with empty providers.

```text
codex: available=True reason=Codex CLI is ready for paper chat.
claude_cli: available=True reason=Claude Code CLI is ready for paper chat.
opencode: available=True reason=OpenCode CLI is ready for paper chat.
openai_compatible: available=False reason=Create an openai_compatible provider with a base_url, then run healthcheck.
```

This is a capability probe. It is not a live paper answer.

## Live paper Q&A (2026-08-18)

Command: `scripts/live_phase1_qa.py` with
`OPEN_ALPHAXIV_CODEX_ENABLED=true`, `OPEN_ALPHAXIV_CLAUDE_ENABLED=true`,
`OPEN_ALPHAXIV_OPENCODE_ENABLED=true`. Local uploaded PDF fixture in
`data/live-qa/` (gitignored). Question: "In one short sentence, what is
this document about?"

First run, before adapter fixes:

```text
codex: ok=false error starts with usage limit; retry after Aug 20th, 2026 1:52 PM
claude_cli: ok=false Error: Input must be provided either through stdin or as a prompt argument when using --print
opencode: ok=false OpenCode returned an empty answer.
```

Claude root cause, reproduced on Claude Code 2.1.233: `--allowedTools` is
variadic. Command
`claude -p --output-format text --allowedTools "" "<prompt>"` exits 1 with
the official missing-input error. `claude -p "<prompt>" --output-format text`
and stdin both return `pong` for a one-word probe
(`https://code.claude.com/docs/en/errors`).

OpenCode root cause, reproduced on OpenCode 1.14.50: `opencode run --format
default <prompt>` with only `subprocess` `cwd=` set to an empty temp
directory returns exit 0 and empty stdout. The same prompt with
`--dir <cwd>` returns a text answer.

Second run, after those two adapter fixes:

```text
codex: ok=false same usage-limit error; retry after Aug 20th, 2026 1:52 PM
claude_cli: ok=true preview=It's a placeholder test fixture — a locally uploaded PDF ("Live QA fixture") in Open AlphaXiv whose full text failed to extract, leaving only a boilerplate abstract about local storage for reading, search, graph building, and paper Q&A.
opencode: ok=true preview=This document is a local test fixture PDF uploaded into Open AlphaXiv, used to exercise local reading, search, graph construction, and paper question-answering functionality.
mcp_tools: search_arxiv, ingest_paper, list_library, get_paper_text, query_paper_pages, save_note, list_notes
live_qa_exit:0
```

HTTP `tools/list` is the in-process MCP surface. Cursor Agent UI listing
was not driven from this process.

## Manual checks still open

| Check | Status |
| --- | --- |
| `codex exec` on an ingested paper | Ran. Host Codex is over its usage limit until 2026-08-20 13:52. |
| `claude -p` on the same paper | Ran after the stdin fix. Answered the fixture question. |
| Cursor Agent listing MCP tools from `/mcp` | Not run from the Cursor agent UI. HTTP `tools/list` returned the seven tools above. |
| OpenAI-compatible answer with a real key or Ollama | Not run. Healthcheck and chat JSON shape are covered by httpx fakes. |
