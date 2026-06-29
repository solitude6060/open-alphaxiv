# Research Discussions And Grounding Snapshots Plan

## Goal

Add project-level research discussions and grounding snapshots so a researcher
can discuss a project with an LLM using durable project state, notes, paper
evidence, experiment runs, artifact references, and code/data references.

This PR is stacked on PR #7 because discussions depend on research projects,
notes, evidence links, and experiment runs.

## First-Principles Check

The user need is not only another chat box. A useful research discussion must
preserve:

- the project context available when the discussion happened
- the exact notes, paper passages, experiment runs, and artifacts included
- the user and assistant messages tied to that context
- a frozen snapshot that can be re-read, exported, or used later without
  silently changing under the researcher

Therefore the minimum PR D object model is:

- `research_discussions`
- `research_discussion_messages`
- `grounding_snapshots`

The snapshot is load-bearing. Without it, later readers cannot tell whether an
LLM answer was based on the current project state or an older set of evidence.

## Scope

In this PR:

- Add SQLite tables for project discussions, messages, and grounding snapshots.
- Add service and API workflows for create/list/get discussion and messages.
- Add snapshot generation from project state, questions, notes, links,
  experiment runs, and artifacts.
- Link discussion messages through `research_links` using the existing
  `discussion_message_id` owner path.
- Add project Markdown export sections for discussions and snapshots.
- Add a lightweight Discussions section to the Research UI.

Out of scope:

- Calling an external LLM from project discussions.
- Automatic codebase indexing.
- Global full-text search.
- Dashboard/status reporting.
- Multi-user permissions.

## API Contract

Discussions:

- `POST /api/research/discussions`
- `GET /api/research/discussions`
- `GET /api/research/discussions/{discussion_id}`
- `POST /api/research/discussions/{discussion_id}/messages`

Grounding snapshots:

- `POST /api/research/projects/{project_id}/grounding-snapshots`
- `GET /api/research/projects/{project_id}/grounding-snapshots`
- `GET /api/research/grounding-snapshots/{snapshot_id}`

## Tests First

Service tests:

- Create a discussion under a project.
- Add user and assistant discussion messages.
- Create a grounding snapshot and verify it includes project state, questions,
  notes, research links, experiment runs, and artifacts.
- Create a discussion-message-owned `research_links` row and verify the existing
  owner constraint supports it.
- Export a project and verify discussions and grounding snapshots are readable.

API tests:

- Exercise discussion create/list/get/message workflows through HTTP.
- Exercise grounding snapshot create/list/get through HTTP.
- Verify unknown project/discussion/snapshot IDs return 404.

Frontend verification:

- `npm run build` must pass.
- The Research panel must show discussion entry and snapshot actions without
  breaking notes or experiment runs.

## Acceptance Criteria

- A user can create a project discussion.
- A user can record discussion messages.
- A user can freeze a grounding snapshot for the project.
- Snapshot content includes project state, notes, evidence, experiment runs,
  and artifacts.
- Discussion messages can own research links through `discussion_message_id`.
- Project export includes discussions and grounding snapshots.
