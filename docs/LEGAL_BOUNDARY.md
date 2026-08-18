# Legal Boundary for a Local Paper Workspace

Survey date: 2026-08-17

This document states the recreation boundary for this repository. It is not
legal advice. It records the primary-source rules that the product contract
must obey.

## First-principles audit

### 1. Need / constraint

- Stated need: recreate alphaXiv in a form that stays inside a defensible
  legal range, and use already-paid coding-agent subscriptions plus ordinary
  model APIs.
- Underlying need: a local research reading surface with discovery, PDF
  reading, grounded questions, notes, related-work views, and a way for the
  user's existing Claude Code / Codex / Cursor / OpenCode / Copilot clients
  to operate on that library.
- Same? The workflow overlap is the need. Copying alphaXiv's brand, hosted
  corpus, community graph, or private APIs is not required to serve it.

### 2. Inherited assumption check

- Assumption: a "complete clone" must scrape or call alphaxiv.org, reuse the
  name, and wrap Cursor or Claude Pro OAuth inside this web app.
- Verified for this case? No. The commercial product itself tells agents to
  connect through MCP (`https://www.alphaxiv.org/docs/mcp`, fetched
  2026-08-17). Anthropic's Claude Code legal page restricts OAuth to native
  Anthropic apps (`https://code.claude.com/docs/en/legal-and-compliance`,
  fetched 2026-08-17). arXiv forbids redistributing most PDFs from your own
  servers (`https://info.arxiv.org/help/api/tou.html`, fetched 2026-08-17).

### 3. Ground-truth verification

| Claim | Verification | Result |
| --- | --- | --- |
| arXiv metadata is CC0 | arXiv API Terms of Use, "Things that you can (and should!) do" | True |
| Personal/research use of e-print content is allowed | Same ToU: "Retrieve, store, and use the content of arXiv e-prints for your own personal use, or for research purposes." | True |
| Publicly storing and serving arXiv PDFs is forbidden without a redistributable license | Same ToU: "Things that you must not do" | True |
| Bulk/robot PDF harvest from arxiv.org is restricted | `https://info.arxiv.org/help/robots.html`; bulk path is S3/Kaggle | True |
| `/pdf` is allowed in robots.txt with crawl-delay | `https://arxiv.org/robots.txt`, User-agent `*`, `Allow: /pdf`, `Crawl-delay: 15` | True |
| Semantic Scholar API requires attribution and obeys S2 data licenses | `https://www.semanticscholar.org/product/api/license`, fetched 2026-08-17 | True |
| alphaXiv exposes an official MCP for agents | `https://www.alphaxiv.org/docs/mcp` | True |
| Claude Pro/Max OAuth is not a third-party developer credential | Claude Code legal-and-compliance page | True |

### 4. Verdict

This is a valid build decision: local-first independent implementation against
public scholarly APIs, original UI and brand, MCP for the user's own agents,
official CLI binaries where the vendor documents non-interactive use.

### 5. Review

No code change in this pass. The boundary below is the merge gate for later
PRs.

## Allowed

- Independently implement a paper discovery, reading, question, note, and
  related-work workspace.
- Use the arXiv API / OAI-PMH for descriptive metadata. Rate limit: one
  request every three seconds, one connection, across machines under the
  operator's control (`https://info.arxiv.org/help/api/tou.html`).
- Cache PDFs on the operator's machine for personal or research use. Always
  keep a landing URL back to `https://arxiv.org/abs/<id>`.
- Accept user-uploaded PDFs that the user already has the right to possess.
- Use Semantic Scholar API data under the licenses that accompany that data,
  with an on-screen "Semantic Scholar" attribution when S2 data is shown
  (`https://www.semanticscholar.org/product/api/license`, 17 May 2023).
  A second live page, `https://api.semanticscholar.org/license/`, is stricter
  (internal non-commercial ML/evaluation language). Phase 2 graph work must
  re-read both texts before any public or commercial display of S2 data.
- Use OpenAI-compatible HTTP APIs with the user's own keys.
- Spawn the official `codex exec` binary with the user's existing Codex login
  or `CODEX_API_KEY` (`https://developers.openai.com/codex/noninteractive`).
- Spawn the official `claude` CLI for the same logged-in user on that
  machine. Do not extract OAuth tokens. Do not reimplement Claude Code.
- Expose this app as an MCP server so Cursor, Claude Code, Codex, Copilot,
  and VS Code remain the agent clients.
- Use GitHub Copilot SDK only through documented GitHub OAuth, stored CLI
  login, env tokens, or BYOK
  (`https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/authenticate`).
- Optionally, later, spawn Cursor `agent -p` or call `@cursor/sdk` with the
  user's `CURSOR_API_KEY` or `agent login`
  (`https://cursor.com/docs/cli/headless`, `https://cursor.com/docs/sdk/typescript`).

## Forbidden

- Use `alphaXiv`, `alphaxiv`, or confusingly similar marks as a public
  product name, logo, or domain. Prefixing `open-` does not remove that
  risk: the distinctive element remains `alphaxiv`. See
  `docs/PRODUCT_EVALUATION_2026-08-17.md` (Naming). The commercial company
  is an active venture-backed product (PR Newswire seed announcement,
  `https://www.prnewswire.com/news-releases/alphaxiv-raises-7m-seed-round-to-bridge-the-ai-research-to-practice-divide-302619615.html`).
  USPTO registration was not independently confirmed in this session; brand
  use in commerce is enough to treat the mark as high-risk for a public
  competing product. A private localhost folder name is a different, lower
  enforcement tier.
- Copy alphaXiv CSS, logos, unique copy, generated reports, or frontend
  assets.
- Call `https://api.alphaxiv.org/` or scrape `https://www.alphaxiv.org/`.
  Unofficial wrappers such as `petroslamb/alphaxiv-py` are out of bounds.
- Store and serve arXiv PDFs, source, or HTML to other people from this
  project's servers unless the paper's own license permits redistribution.
- Circumvent arXiv or Semantic Scholar rate limits.
- Claim endorsement by arXiv, Semantic Scholar, OpenAI, Anthropic, GitHub, or
  alphaXiv.
- Extract Claude / ChatGPT / Copilot cookies or OAuth refresh tokens and
  replay them through a custom HTTP client.
- Ship OpenCode (or similar) plugins that Anthropic states are prohibited for
  Claude Pro/Max OAuth (`https://opencode.ai/docs/providers/`, Anthropic
  section, fetched 2026-08-17).
- Bundle the Claude Agent SDK against a user's Pro/Max OAuth token. The
  Agent SDK path requires a Console API key
  (`https://code.claude.com/docs/en/legal-and-compliance`).

## Local vs public hosting

| Mode | PDF cache | Discovery metadata | Agent calls |
| --- | --- | --- | --- |
| Single-user localhost / trusted LAN | Allowed as personal/research use | arXiv API + optional S2 | User's own CLI login or API keys |
| Public multi-tenant SaaS | Forbidden for default arXiv license papers | Metadata only, link out for PDFs | API keys only; no pooled subscriptions |

This repository's product contract is the first row. Public SaaS is a later
company decision and requires a different legal review.

## Per-paper license handling

Most arXiv e-prints use the arXiv non-exclusive distribution license, which
does not grant third parties redistribution rights
(`https://info.arxiv.org/help/license/reuse.html`). A smaller set uses
Creative Commons licenses, recorded in OAI-PMH metadata.

Required behavior:

1. Persist `landing_url` to the arXiv abstract page on every imported paper.
2. Persist license URL when OAI-PMH or the abstract page exposes it.
3. UI download actions link to arXiv, not to a public copy hosted by this app.
4. Local file serving is bound to the same-origin authenticated session of the
   operator. It is not an open `/pdfs/` URL on the internet.

## Agent-subscription boundary

See `docs/AGENT_ARCHITECTURE.md`. The short rule:

- The paper app owns papers, notes, and retrieval.
- The coding agent the user already pays for remains that vendor's official
  client (Claude Code, Codex, Cursor, OpenCode, Copilot).
- This app talks to those clients through MCP, or it may spawn the official
  CLI on the same machine.
- API keys are the path for in-process generation inside this app.
