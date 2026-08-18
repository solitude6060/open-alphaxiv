# ADR 0003: MCP-First Agent Subscriptions

## Status

Accepted 2026-08-17. Implement against `docs/AGENT_ARCHITECTURE.md` and
`docs/PRODUCT_CONTRACT.md`, not against the 2026-06 SPEC provider appendix.

## Context

The user already pays for coding-agent subscriptions and wants those, plus
ordinary APIs, inside this paper workspace. The current code only spawns
`codex exec` (`app/services.py:2536-2546`). Docs also promise a provider
abstraction that is not implemented as a live HTTP client
(`docs/SPEC.md` Provider Adapter Contract; `app/services.py:495-509`).

## Decision

Ship three runtimes as specified in `docs/AGENT_ARCHITECTURE.md`:

1. MCP server so Cursor / Claude Code / Codex / Copilot remain the clients.
2. Official CLI spawn for in-app Ask Paper (`codex exec`, `claude -p`,
   `opencode run`).
3. OpenAI-compatible HTTP for API keys and embeddings.

## Alternatives considered

- In-process Claude Agent SDK using the user's Pro/Max login.
  Invalidated: Anthropic requires Console API keys for the SDK and forbids
  third-party routing of Free/Pro/Max OAuth
  (`https://code.claude.com/docs/en/legal-and-compliance`).
- Wrap Cursor as a hidden child process that scrapes the IDE.
  Invalidated as a product path. Cursor documents MCP
  (`https://cursor.com/docs/mcp`). It also documents `agent -p`
  (`https://cursor.com/docs/cli/headless`, fetched 2026-08-17) and
  `@cursor/sdk` with `CURSOR_API_KEY`
  (`https://cursor.com/docs/sdk/typescript`, fetched 2026-08-17).
  Phase 1 still uses MCP for Cursor. An in-app Cursor adapter is optional
  later and must use those official auth surfaces, not cookies.
- OpenAI-compatible HTTP only.
  Viable but fails the subscription requirement for Cursor and Claude Code.
- MCP only, no in-app assistant.
  Viable and safest. Rejected as the sole runtime because the existing
  reader already has in-app Ask Paper via Codex and that path is documented
  for `codex exec`.

## Consequences

- Phase 1 of `docs/ALPHAXIV_RECREATION_PLAN.md` is the agent runtime, not
  more research-notebook tables.
- Provider settings UI must distinguish: MCP connected, CLI available, HTTP
  key healthy.
- Tests must cover capability probes and must not require live vendor
  accounts in CI.
