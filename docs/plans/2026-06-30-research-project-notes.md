# Research Project And Notes MVP Plan

## Goal

Add the first durable research workspace layer: projects, questions, Markdown
notes, evidence links, paper-passage capture, Ask Paper answer capture, and
project Markdown export.

This PR intentionally stops before experiment runs, project-level LLM
discussions, grounding snapshots, and global search. Those remain PR C, PR D,
and PR E.

## First-Principles Check

The user need is persistent research state, not only a note text box. A useful
MVP must preserve:

- what research direction the note belongs to
- what question or current state the project is tracking
- which paper passage or chat answer supports the note
- how the note can be exported without opening the app

Therefore the minimum PR B object model is:

- `research_projects`
- `research_questions`
- `research_notes`
- `research_links`

The evidence link is load-bearing. Without it, notes become untraceable prose
and cannot support later Codex discussions or project exports.

## Scope

In this PR:

- Add SQLite tables for projects, questions, notes, and links.
- Enforce `research_links` ownership with a SQLite `CHECK` constraint.
- Require `relation` on every link.
- Add service and API methods for project, note, question, link, and export
  workflows.
- Add paper-passage to note capture.
- Add Ask Paper answer to note capture.
- Add a Research UI panel with project list, note editor, evidence list, and
  export link.
- Use soft archive status instead of hard delete.

Out of scope:

- Experiment run records.
- Project-level LLM discussion.
- Frozen grounding snapshots.
- SQLite full-text search.
- Code path ingestion into LLM context.
- Multi-user permissions.

## API Contract

Projects:

- `POST /api/research/projects`
- `GET /api/research/projects`
- `GET /api/research/projects/{project_id}`
- `PATCH /api/research/projects/{project_id}`
- `GET /api/research/projects/{project_id}/export.md`

Notes:

- `POST /api/research/notes`
- `GET /api/research/notes`
- `GET /api/research/notes/{note_id}`
- `PATCH /api/research/notes/{note_id}`
- `POST /api/research/notes/{note_id}/links`
- `GET /api/research/notes/{note_id}/links`

Questions:

- `POST /api/research/questions`
- `GET /api/research/questions`
- `PATCH /api/research/questions/{question_id}`

Paper and chat capture:

- `POST /api/papers/{paper_id}/research-notes`
- `POST /api/chat/messages/{message_id}/research-note`

## Tests First

Service tests:

- Create a project with a slug and active status.
- Create a research question under a project.
- Create a note under a project with tags and Markdown body.
- Link a note to a paper passage and verify relation/link metadata.
- Create a paper-passage note and verify both `research_notes` and
  `research_links` rows exist.
- Create an Ask Paper answer note and verify a `chat_message` evidence link.
- Archive a note and project through status updates, not hard delete.
- Export a project and verify readable citations such as
  `[Paper Title, p.3]`.

API tests:

- Exercise the same core workflow through HTTP.
- Verify unknown project/paper/message IDs return 404.
- Verify invalid link payloads return 400.

Frontend verification:

- `npm run build` must pass.
- The Research panel must not break the existing paper reader flow.

## Acceptance Criteria

- A user can create a project.
- A user can record a research question and current project state.
- A user can create and edit a Markdown note.
- A user can save a selected paper passage into a note.
- A user can save an Ask Paper answer into a note.
- Every captured note shows linked paper or chat evidence.
- Project export is readable Markdown with citations and notes.
- No UI hard-delete path removes linked projects or notes.
