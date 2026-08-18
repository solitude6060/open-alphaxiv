# Product Evaluation — 2026-08-17

This file answers three questions from first principles:

1. What counts as a good product for this repository.
2. Whether the string `alphaXiv` / `open-alphaxiv` is a lawsuit-grade risk.
3. How coding-agent subscriptions may be used, given that OpenClaw embeds Codex.

It is an engineering risk assessment, not legal advice.

## First-principles audit

### 1. Need / constraint

- Stated need: recreate alphaXiv completely, stay in a range that is
  unlikely to produce a lawsuit, and spend already-paid coding-agent
  subscriptions.
- Underlying need: a daily paper loop that is faster than alphaxiv.org for
  this operator, on this machine, with models already paid for.
- Same? Workflow overlap is the need. The commercial brand, hosted comments
  graph, and alphaxiv.org APIs are not required to serve it.

### 2. Inherited assumption check

- Assumption A: prefixing `open-` makes a competitor's coined mark safe.
- Assumption B: "complete recreation" means matching alphaXiv's public
  social product.
- Assumption C: because OpenClaw uses ChatGPT/Codex OAuth, any third-party
  wrapper of any vendor subscription is equally allowed.
- Verified? A is false as a legal rule (see Naming). B is false as a product
  rule (see Good product). C is false as a cross-vendor rule (see Agents);
  it is directionally true for OpenAI Codex's documented embed surfaces.

### 3. Ground-truth verification

| Claim | Verification | Result |
| --- | --- | --- |
| alphaXiv Inc. is in commerce under that name | PR Newswire 2025-11-19 seed round; alphaxiv.org; Chrome Web Store extension | True |
| USPTO registration of ALPHAXIV | Not confirmed in this session | Unknown |
| `open-` removes confusion | US likelihood-of-confusion tests look at the distinctive element; `open` is descriptive | The prefix is a weak distinguisher |
| OpenAI documents embedding Codex in another product | `https://developers.openai.com/codex/app-server`: "deep integration inside your own product"; engineering post `https://openai.com/index/unlocking-the-codex-harness/` | True |
| `codex exec` is documented for scripts | `https://developers.openai.com/codex/noninteractive` | True |
| OpenClaw documents ChatGPT/Codex OAuth outside Codex CLI | `https://docs.openclaw.ai/concepts/oauth` | True as OpenClaw's claim; not an OpenAI ToS excerpt |
| Anthropic forbids third-party Pro/Max OAuth routing | `https://code.claude.com/docs/en/legal-and-compliance` | True for that vendor |

### 4. Verdict

Valid build decision: independent local paper product, original public
name, OpenAI Codex via official `exec` then `app-server`, other agents via
MCP or their official CLI, arXiv/S2 as data.

### 5. Review

No application code in this pass.

## What a good product is here

A good product is the smallest system that repeatedly wins a real job.

The job: a researcher opens a paper, understands it, keeps evidence, and
moves to related work, using models already on the machine.

| Test | Pass condition | Current tree |
| --- | --- | --- |
| Time to first useful answer | Paste arXiv URL → readable PDF + one grounded answer in one sitting | Partial: ingest + Codex work; feed/search missing |
| Subscription spend | Codex / Claude Code / Cursor seats used without a second API bill when those clients exist | Codex `exec` only |
| Honesty | Related-work panel shows real papers | Fail: synthetic nodes in `app/services.py:1176` |
| Locality | Papers and notes stay on the operator disk | Pass |
| Survival | Public listing does not invite a straightforward trademark or ToS complaint | Fail while the product mark is `Open AlphaXiv` |
| Completeness | Daily loop, not a demo of every notebook table | Research notebook is ahead of discovery |

Features that do not change the next continue/stop decision: public
comments, researcher directory, events, audio, Pro billing, fake graphs.

alphaXiv's own good-product loop, observed from the public site and MCP
docs, is: discover → open PDF → ask with citations → notes/folders →
similar papers → (optional) GitHub. Recreating that loop locally is the
product. Recreating their community graph is a different company.

## Naming: will `open-alphaxiv` get you sued?

### Short answer

- **Private repo / localhost use of the current folder name:** low
  enforcement probability. You are not offering a competing public service
  under their mark.
- **Public GitHub + README that says this is an alphaXiv clone:** medium.
  Cease-and-desist is the realistic first move if the project gets traffic.
  A lawsuit is costlier for them than a letter; it is still possible.
- **Public product, domain, or Chrome extension using `alphaXiv` / `Open
  AlphaXiv`:** high. Same category, same distinctive coined word, funded
  company in active commerce.
- **Does `open-` make it safe?** No. It is a weak, descriptive prefix. The
  dominant element remains `alphaxiv`.

### Why `open-` is not a shield

Likelihood of confusion asks whether ordinary buyers would think the
junior product comes from, or is sponsored by, the senior user. Courts
compare marks in their entireties, but the distinctive part drives the
impression. `OPEN` is commonly disclaimed. `ALPHAXIV` is a coined blend of
alpha + arXiv used in commerce for a paper-reading service.

Close analogues:

- `OpenOffice.org` was the project's own chosen mark, later owned by Apache.
  It is not a template for taking a competitor's mark and prefixing `Open`.
- The LibreOffice fork chose a **new** distinctive name.
- `alphaxiv-open` and `little-alphaxiv` exist on GitHub. That shows
  community practice and, so far, no public enforcement found in this
  survey. Other people's unenforced risk is not a license.

US common-law trademark rights arise from **use in commerce**, not only
from a USPTO registration. Registration was not confirmed this session;
commerce under the name is confirmed (site, extension, $7M seed PR).

### Recommended naming policy

| Surface | Policy |
| --- | --- |
| Local git remote / private working title | `open-alphaxiv` may remain until a public push |
| README one-liner | "Independent local paper workspace. Not affiliated with alphaXiv." |
| Public product name, window title, Docker Hub, domain | Original mark with no `alphaxiv` substring |
| Comparison text | Nominative: "inspired by the public alphaXiv reading workflow" once, with a disclaimer |

Candidate public names stay unchosen here; the user picks. The recreation
plan does not block Phase 1 on a rename. It blocks **public marketing** on
a rename.

## Agents: OpenClaw vs this repo

### OpenAI Codex

OpenAI published a first-party embed path:

- Scripts/CI: `codex exec`
  (`https://developers.openai.com/codex/noninteractive`).
- Rich product UI: `codex app-server`
  (`https://developers.openai.com/codex/app-server`), described as the
  interface for "a deep integration inside your own product", including
  authentication, history, approvals, streamed events. OpenAI's engineering
  post frames JetBrains and Xcode as the intended class of clients
  (`https://openai.com/index/unlocking-the-codex-harness/`).

This repository already uses `codex exec` (`app/services.py:2536-2546`).
That matches the documented script path. OpenClaw goes further: ChatGPT
OAuth and the Codex app-server harness
(`https://docs.openclaw.ai/concepts/oauth`,
`https://docs.openclaw.ai/providers/openai`). OpenClaw's docs state
"OpenAI Codex OAuth is explicitly supported for use outside the Codex CLI."
That sentence is OpenClaw's documentation. It is consistent with OpenAI
shipping Sign in with ChatGPT on Codex surfaces and an open-source
app-server. It is not a substitute for OpenAI counsel.

**Product implication:** Codex-in-this-app is the lowest-risk subscription
path among vendors. Phase 1 keeps `codex exec`. The good in-app assistant
(streaming, ChatGPT sign-in UI, approvals) should move to `codex
app-server` the way OpenClaw and IDE partners do, spawning the official
binary rather than reimplementing `auth.openai.com` ourselves.

### Anthropic Claude Code

Anthropic's published rule is the opposite shape: OAuth is for native
Anthropic apps; third-party products must use Console API keys
(`https://code.claude.com/docs/en/legal-and-compliance`). OpenClaw currently
documents `claude -p` reuse as something Anthropic staff told them is
allowed again (`https://docs.openclaw.ai/concepts/oauth`). That is
second-hand. This project will:

- Prefer MCP so Claude Code stays the client.
- Optionally spawn the official `claude` binary for the same logged-in
  user.
- Not become an OAuth client that stores Claude refresh tokens.
- Use API keys for any in-process SDK.

### Cursor

MCP is the documented join for this app (`https://cursor.com/docs/mcp`).
Cursor also documents a headless CLI `agent -p`
(`https://cursor.com/docs/cli/headless`, fetched 2026-08-17) and
`@cursor/sdk` with `CURSOR_API_KEY`
(`https://cursor.com/docs/sdk/typescript`, fetched 2026-08-17). Phase 1
does not spawn Cursor in-process. An optional later adapter must use those
auth surfaces, not IDE cookies.

### Cross-vendor rule

"OpenClaw does X with Codex" licenses **Codex-shaped** integration
(official binary, app-server, documented ChatGPT sign-in). It does not
license cookie replay, alphaxiv.org scraping, or Claude OAuth extraction.

## Project evaluation (continue / adjust / stop)

| Axis | Score | Note |
| --- | --- | --- |
| Job-to-be-done clarity | High | Daily paper loop |
| Current code as a start | Medium | Reader + Codex + notes exist; discovery and graph are fake or missing |
| Legal envelope if local-only + original public name | Acceptable | See `docs/LEGAL_BOUNDARY.md` |
| Legal envelope if public "Open AlphaXiv" clone | Poor | Naming section |
| Agent envelope for Codex | Good | Official exec/app-server |
| Agent envelope for Cursor | Good if MCP | Phase 1 |
| Agent envelope for Claude subscription | Guarded | MCP first; CLI spawn optional |
| Effort to a daily-usable loop | Three phases after contract accept | Plan file |

**Recommendation:** continue. Adjust the public name. Do not stop. Do not
expand the research notebook until Phase 1–3 of
`docs/ALPHAXIV_RECREATION_PLAN.md` are green.

## Planning adjustments after this evaluation

1. Phase 1 stays MCP + CLI adapters + live HTTP. Codex remains `exec`.
2. Add Phase 1b (after Phase 1 green): optional `codex app-server` for
   streamed in-app Codex, following OpenAI's embed docs. Not a Phase 1
   blocker.
3. Public rename is a Phase 0 marketing gate, not a Phase 1 code gate.
4. README disclaimer ships with the next docs commit.
