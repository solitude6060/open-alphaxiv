# Phase 1 Agent Runtime Implementation Plan

**Status:** implemented 2026-08-18. Evidence: `docs/PHASE1_EVIDENCE.md`.
Do not re-implement adapters or MCP from this checklist.

> **For agentic workers:** This plan is an archive of the Phase 1 task
> split. Remaining checkboxes are historical process, not open work.

**Goal:** In-app Ask Paper can use Codex, Claude Code CLI, OpenCode, or an
OpenAI-compatible HTTP endpoint; Cursor/Claude Code/Codex can call this
library through MCP.

**Architecture:** Extract a small `AgentAdapter` protocol. Keep paper ingest
on `PaperService`. MCP tools call `PaperService` and `arxiv` connectors
already in the tree.

**Tech Stack:** FastAPI, pytest, httpx mocks, subprocess fakes.

**Spec:** `docs/PRODUCT_CONTRACT.md`, `docs/AGENT_ARCHITECTURE.md`,
`docs/LEGAL_BOUNDARY.md`.

## Global Constraints

- No alphaxiv.org requests.
- No OAuth token extraction.
- Claude adapter runs the `claude` binary; it does not send
  `ANTHROPIC_API_KEY` unless the user configured HTTP Anthropic separately.
- MCP localhost only.
- Do not expand `app/services.py` with the new adapters; put them under
  `app/agents/` and `app/mcp/`.

---

### Task 1: AgentAdapter protocol and Codex extraction

**Files:**
- Create: `app/agents/__init__.py`
- Create: `app/agents/protocol.py`
- Create: `app/agents/codex.py`
- Modify: `app/services.py` — `codex_answer` / `_run_codex_exec_prompt` import
  from `app.agents.codex`
- Test: `tests/test_agents.py`

**Interfaces:**
- Produces: `AgentRunResult`, `run_codex_exec(prompt, options) -> AgentRunResult`
- Consumes: existing `codex_options()` in `app/main.py:733`

- [ ] **Step 1: Write the failing test**

```python
from app.agents.protocol import AgentRunResult

def test_agent_run_result_requires_adapter_name():
    result: AgentRunResult = {
        "ok": True,
        "text": "hello",
        "adapter": "codex",
        "binary_path": "/usr/bin/codex",
        "latency_ms": 1,
        "exit_code": 0,
        "stderr_preview": "",
        "model": "codex-local-agent",
    }
    assert result["adapter"] == "codex"
```

Add a subprocess fake test that the extracted Codex runner still raises
`RuntimeError` on non-zero exit, matching
`tests/test_services.py` Codex failure cases.

- [ ] **Step 2: Run test to verify it fails**

Run: `env PYTHONPATH=.:.deps python3 -m pytest tests/test_agents.py -v`
Expected: FAIL with import error for `app.agents`

- [ ] **Step 3: Write minimal implementation**

Move `_prepare_codex_exec`, `_run_codex_exec_prompt`,
`codex_credentials_available`, and `resolve_executable` to
`app/agents/codex.py`. Re-export from `app.services` so existing tests keep
importing the old names.

- [ ] **Step 4: Run tests**

Run: `env PYTHONPATH=.:.deps python3 -m pytest tests/test_agents.py tests/test_services.py tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents app/services.py tests/test_agents.py
git commit -m "$(cat <<'EOF'
refactor: extract Codex CLI runner into an agent adapter

Paper Q&A and research discussions keep the same exec flags while
the agent package becomes the home for Claude Code and OpenCode.
EOF
)"
```

---

### Task 2: Claude Code CLI adapter

**Files:**
- Create: `app/agents/claude_cli.py`
- Modify: `app/config.py` — `claude_enabled`, `claude_cli_path`,
  `claude_timeout_seconds`
- Test: `tests/test_agents.py`

**Interfaces:**
- Produces: `run_claude_print(prompt, options) -> AgentRunResult`
- Command: `[cli, "-p", "--output-format", "text"]` with the prompt on stdin
  inside an isolated temp directory. Do not pass `--bare`. Do not pass
  `--allowedTools` with an empty value: Claude Code 2.1 treats that flag as
  variadic and consumes the prompt.
- Probe: `shutil.which(cli)` and `--version`.

- [ ] **Step 1: Write the failing test**

```python
from app.agents.claude_cli import run_claude_print

def test_claude_cli_uses_print_flag(monkeypatch, tmp_path):
    recorded = {}

    def fake_run(command, **kwargs):
        recorded["command"] = command
        recorded["cwd"] = kwargs.get("cwd")
        return type("R", (), {"returncode": 0, "stdout": "cited answer", "stderr": ""})()

    monkeypatch.setattr("app.agents.claude_cli.subprocess.run", fake_run)
    monkeypatch.setattr("app.agents.claude_cli.resolve_executable", lambda path: "/bin/claude")
    result = run_claude_print("What is attention?", {"enabled": True, "cli_path": "claude", "timeout_seconds": 30})
    assert result["ok"] is True
    assert "-p" in result["text"] or "-p" in recorded["command"]
    assert "--bare" not in recorded["command"]
    assert result["text"] == "cited answer"
```

Fix the assertion to check `recorded["command"]` only; do not require `-p`
inside the answer text.

- [ ] **Step 2: Run test to verify it fails**

Run: `env PYTHONPATH=.:.deps python3 -m pytest tests/test_agents.py::test_claude_cli_uses_print_flag -v`
Expected: FAIL with import error

- [ ] **Step 3: Write minimal implementation**

Raise `ValueError` when disabled or binary missing. Map timeout and OSError
to `RuntimeError` like Codex. Never read `~/.claude` credentials into Python.

- [ ] **Step 4: Run tests**

Run: `env PYTHONPATH=.:.deps python3 -m pytest tests/test_agents.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/claude_cli.py app/config.py tests/test_agents.py
git commit -m "$(cat <<'EOF'
feat: add Claude Code CLI print adapter for paper questions

Spawn the official claude binary with -p so in-app answers can use
a host Claude Code login without copying OAuth tokens.
EOF
)"
```

---

### Task 3: OpenCode adapter

**Files:**
- Create: `app/agents/opencode.py`
- Test: `tests/test_agents.py`

**Interfaces:**
- Command: `[cli, "run", "--format", "default", "--dir", cwd, prompt]`
  inside an isolated temp directory. `--dir` is required; subprocess `cwd=`
  alone yields exit 0 and empty stdout on OpenCode 1.14.50.
- Optional `--model` from settings.
- Do not add Claude Pro/Max plugin flags.

- [ ] **Step 1: Write failing test** analogous to Task 2, asserting
  `recorded["command"][1] == "run"`.

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Minimal implementation**

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit** `feat: add OpenCode run adapter for paper questions`

---

### Task 4: OpenAI-compatible HTTP generation and real healthcheck

**Files:**
- Create: `app/agents/openai_compatible.py`
- Modify: `app/services.py` `healthcheck_provider`
- Modify: `.env.example` comments to match real behavior
- Test: `tests/test_agents.py`, `tests/test_api.py`

**Interfaces:**

```python
def chat_completions(base_url: str, api_key: str, model: str, messages: list[dict], timeout_s: float) -> str: ...
```

POST `{base_url}/chat/completions` with `Authorization: Bearer`. Trim trailing
slash on `base_url`. Reject `base_url` whose host is not localhost and not
https (SSRF: no `file://`, no link-local except explicit localhost allow
list).

Healthcheck: GET `{base_url}/models` or a 1-token chat; store
`health_status=ok|failed` and a real `reason`.

- [ ] **Step 1: Write failing tests** for request JSON shape, redaction, and
  rejected `http://169.254.169.254/`.

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement client + healthcheck branch when
  `provider_type == "openai_compatible"`**

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit** `feat: call OpenAI-compatible chat APIs for paper answers`

---

### Task 5: Agent registry, status endpoint, chat answer_mode

**Files:**
- Create: `app/agents/registry.py`
- Modify: `app/main.py` `GET /api/agents/status`, `ChatAsk.answer_mode`
- Modify: paper chat handler to dispatch adapters
- Modify: `web/src/main.tsx` agent picker
- Test: `tests/test_api.py`

**Interfaces:**
- `answer_mode` enum: `mock`, `codex`, `claude_cli`, `opencode`,
  `openai_compatible`
- Status JSON keys listed in `docs/ALPHAXIV_RECREATION_PLAN.md` Phase 1

- [ ] **Step 1: Failing API test** that `/api/agents/status` returns all keys
  and that `answer_mode=openai_compatible` without a healthy provider returns
  HTTP 400 with a setup reason.

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Wire dispatch. Keep mock and Codex behavior byte-compatible
  for existing tests.**

- [ ] **Step 4: pytest + `cd web && npx tsc --noEmit`**

- [ ] **Step 5: Commit** `feat: expose agent status and additional Ask Paper modes`

---

### Task 6: MCP server

**Files:**
- Create: `app/mcp/__init__.py`
- Create: `app/mcp/tools.py`
- Create: `app/mcp/server.py`
- Modify: `app/main.py` mount `/mcp`
- Modify: `README.md` Cursor / Claude Code / Codex client snippets
- Test: `tests/test_mcp.py`

**Interfaces:**

Tools:

- `search_arxiv(query: str, max_results: int = 10)`
- `ingest_paper(arxiv_id: str)`
- `list_library()`
- `get_paper_text(paper_id: int)`
- `save_note(project_id: int, title: str, body_markdown: str)`

Use the official Python MCP SDK if it is already an acceptable dependency;
otherwise implement a minimal JSON-RPC stdio launcher plus a FastAPI
Streamable HTTP endpoint that speaks the MCP tool list/call methods used by
Cursor. Prefer the SDK. Pin the version in `requirements.txt`.

SSRF: `search_arxiv` only calls `export.arxiv.org`. `ingest_paper` reuses
`normalize_arxiv_id`.

- [ ] **Step 1: Failing tests** for tool schemas and `list_library` against
  a temp SQLite store with one paper.

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement tools + mount. Bind to 127.0.0.1 in docs.**

- [ ] **Step 4: pytest pass**

- [ ] **Step 5: Commit** `feat: expose local paper library as an MCP server`

README must include:

```json
{
  "mcpServers": {
    "open-alphaxiv": {
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

and the Claude Code / Codex CLI add commands from
`docs/AGENT_ARCHITECTURE.md`.

---

### Task 7: Manual evidence log

**Files:**
- Create: `docs/PHASE1_EVIDENCE.md` (filled by the operator, not invented)

- [ ] Run the four manual checks in `docs/ALPHAXIV_RECREATION_PLAN.md`
  Phase 1. Record command, exit code, and adapter availability. Do not
  paste secrets.

- [ ] Commit only if the file contains real command output from this
  machine.

---

## Self-review

- Spec coverage: MCP, CLI spawn, OpenAI-compatible HTTP each have a task.
- Legal: no alphaxiv client, no `--bare` Claude subscription path, SSRF
  tests in Task 4.
- Existing Codex tests remain the regression net.
