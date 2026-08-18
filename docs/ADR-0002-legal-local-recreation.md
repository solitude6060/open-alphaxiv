# ADR 0002: Legally Bounded Local Recreation

## Status

Accepted 2026-08-17. Old SPEC/PRD/roadmap files are historical and do not
constrain implementation.

## Context

The repository name and docs describe an "open alphaXiv". The commercial
product alphaXiv is an active company with a hosted corpus, community
features, and an official MCP server. arXiv terms forbid redistributing most
e-prints. Coding-agent vendors restrict how subscriptions may be used.

A pixel-identical public clone would concentrate trademark, copyright,
arXiv redistribution, and vendor ToS risk.

## Decision

1. Recreate the **researcher workflow**, not the hosted social network.
2. Stay local-first. Public multi-tenant PDF hosting is out of scope.
3. Use arXiv, Semantic Scholar, and user uploads as data sources. Do not
   call alphaxiv.org APIs.
4. Keep "Open AlphaXiv" as a private working title until a public rename.
   A public release needs an original mark.
5. Treat `docs/LEGAL_BOUNDARY.md` as a merge gate.

## Alternatives considered

- Call unofficial alphaxiv HTTP APIs for comments and similar-papers.
  Rejected: depends on a competitor's private surface.
- Public SaaS that mirrors alphaxiv.org including PDF serving.
  Rejected: arXiv ToU redistribution clause.
- Drop the product and only use `blazickjp/arxiv-mcp-server`.
  Rejected: that server has no local reading UI, notes, or experiment
  records this user already relies on.

## Consequences

- Community comments, researcher directory, events, and public profiles are
  not v1 features.
- Discovery feed is built from the arXiv API, not from alphaXiv's ranking.
- Docs and UI must link to arXiv abstract pages.
- `docs/SPEC.md` and `docs/PRD.md` remain historical for implemented MVP1
  APIs; product scope follows `docs/PRODUCT_CONTRACT.md`.
