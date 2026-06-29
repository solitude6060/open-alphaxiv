# Research Search And Status Dashboard Plan

## Goal

Add a local research search and status dashboard so a researcher can quickly
see current work state and find projects, questions, notes, experiment runs,
discussions, and grounding snapshots without manually scanning every section.

This PR is stacked on PR #8 because search and dashboard summaries depend on
research projects, notes, evidence, experiment runs, discussions, and snapshots.

## First-Principles Check

The user need is not a general search engine. The minimum useful system must
answer:

- What active research work exists?
- Which questions, notes, runs, discussions, and snapshots are present?
- Which items match a phrase from a paper, experiment, or idea?
- Where should the user click next?

Therefore PR E should ship:

- a deterministic status summary built from local SQLite rows
- a bounded local search endpoint over existing research objects
- a compact dashboard/search UI inside the current Research panel

Out of scope:

- vector search
- background indexing
- ranking models
- remote codebase indexing
- multi-user analytics

## API Contract

Dashboard:

- `GET /api/research/dashboard`

Search:

- `GET /api/research/search?q=<query>&project_id=<optional>`

Search results must be bounded and typed. Each result should expose:

- `type`
- `id`
- `project_id`
- `title`
- `snippet`
- `created_at`

## Tests First

Service tests:

- Create representative research objects.
- Verify dashboard counts and active project summaries.
- Verify search finds projects, questions, notes, experiment runs,
  discussions, messages, and grounding snapshots.
- Verify project-scoped search excludes other projects.
- Verify empty query returns an empty result list.

API tests:

- Exercise dashboard through HTTP.
- Exercise search through HTTP.
- Verify project-scoped search through HTTP.

Frontend verification:

- `npm run build` must pass.
- Dashboard and search UI must render without breaking paper reading,
  notes, experiment runs, or discussions.

## Acceptance Criteria

- A user can see counts for research projects, questions, notes, experiment
  runs, discussions, and grounding snapshots.
- A user can see active project summaries with related object counts.
- A user can search across local research objects.
- A user can scope search to the selected project.
- Search results are typed and readable.
