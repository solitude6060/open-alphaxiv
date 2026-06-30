# Research Workspace Plan

## Purpose

Open AlphaXiv should become a local research workspace, not only a paper
reader. The next product layer should let a researcher continuously record
research notes, experiment progress, current status, paper evidence, codebase
references, and LLM discussions in one local system.

The target workflow is bidirectional:

- From a paper passage, PDF page region, or Ask Paper answer into a research
  note or research discussion.
- From a research note, experiment result, or codebase observation back into a
  paper discussion.
- From a selected set of papers, notes, code files, and experiment data into a
  context pack for Codex or another configured LLM.

## First-Principles Audit

### 1. What Is The User's Actual Need?

The user does not only need "notes." The underlying need is a persistent
research memory system that can preserve:

- research intent and open questions
- paper evidence
- experiment state and results
- codebase observations
- LLM reasoning threads
- links among all of the above

The system should answer: "What do I currently believe, why do I believe it,
what evidence supports it, what experiment changed it, and what should I try
next?"

### 2. What Assumption Is Making This Approach Attractive?

The main inherited assumption is that a Markdown notes panel is enough. That is
not verified for this case because the requested workflow includes experiments,
codebase context, paper citations, and LLM discussion continuity.

### 3. Is The Assumption Verified Or Inherited?

It is inherited. A single note field would store prose, but it would not
preserve source links, experiment provenance, or reusable LLM context. The
current repository already has paper artifacts, chat sessions, and selected
paper context. The missing primitive is not "a text box"; it is a linkable
research object model.

Verification artifacts:

- `docs/PRD.md` already states that notes, summaries, citations, and graph
  snapshots must be exportable.
- `docs/SPEC.md` already models `ChatSession` and `ChatMessage`.
- `app/store.py` currently has `papers`, `artifacts`, `chunks`,
  `chat_sessions`, and `chat_messages`, but no research project, research note,
  experiment run, code reference, or note-link table.

### 4. If The Assumption Were Wrong, What Would Change?

If a plain Markdown note is sufficient, the next implementation would only add
one notes table and one editor. If it is not sufficient, the correct first
implementation is a small graph of research objects:

- project
- note
- discussion
- linked source
- experiment run
- context pack

Because the user's request explicitly includes paper, codebase, experiment
data, and LLM discussion, the richer object model is load-bearing.

### 5. Is This Addressing The Underlying Need Or A Symptom?

This plan addresses the underlying need. It does not only add note-taking UI. It
creates a durable structure for research state, evidence, and model-assisted
discussion that can be traced back to papers, code, and experiment data.

Verdict: valid build decision. Avoid shipping a one-field note feature as the
main solution. A lightweight note editor is useful only if it is backed by
linkable evidence and discussion records.

## Product Shape

### Core Concepts

| Concept | Purpose |
| --- | --- |
| Research Project | A durable workspace for one research direction, hypothesis, or paper-to-code effort. |
| Research Note | A Markdown note with status, tags, source links, and optional parent project. |
| Research Discussion | A continuous LLM conversation scoped to a project, paper set, note set, code paths, or experiment data. |
| Evidence Link | A typed reference from a note or discussion message to a paper, passage, page region, code path, experiment file, or experiment run. |
| Research Question | A tracked question inside a project, used to make progress/status concrete. |
| Experiment Run | A structured record of configuration, metrics, artifacts, logs, and conclusions. |
| Grounding Snapshot | A frozen record of the papers, passages, notes, code references, and experiment summaries used for one LLM discussion. |

### User-Facing Jobs

1. Capture a paper passage into a research note.
2. Capture an Ask Paper answer into a research note.
3. Record current research progress and next actions.
4. Link a note to one or more papers.
5. Link a note to code paths and experiment files.
6. Start a research discussion with selected papers, notes, code, and
   experiment data.
7. Save useful LLM discussion output back into notes.
8. Export a research project as Markdown for writing, sharing, or checkpointing.

## Data Model

### `research_projects`

Fields:

- `id`
- `title`
- `slug`
- `status`: `active`, `paused`, `completed`, `archived`
- `goal`
- `current_state`
- `created_at`
- `updated_at`

### `research_notes`

Fields:

- `id`
- `project_id`
- `title`
- `body_markdown`
- `note_type`: `idea`, `question`, `summary`, `experiment_note`,
  `decision`, `todo`, `meeting`, `literature_note`
- `status`: `draft`, `active`, `resolved`, `archived`
- `tags_json`
- `created_at`
- `updated_at`

### `research_links`

Fields:

- `id`
- `project_id`
- `note_id`
- `discussion_message_id`
- `link_type`: `paper`, `paper_passage`, `paper_region`, `chat_message`,
  `code_path`, `experiment_run`, `experiment_artifact`, `external_url`
- `relation`: `supports`, `contradicts`, `extends`, `implements`, `cites`,
  `mentions`, `questions`
- `target_id`
- `target_uri`
- `label`
- `quote`
- `metadata_json`
- `created_at`

Rules:

- At least one of `note_id` or `discussion_message_id` must be set.
- Enforce `CHECK (note_id IS NOT NULL OR discussion_message_id IS NOT NULL)`
  in SQLite, not only in service validation.
- `note_id` must reference `research_notes(id) ON DELETE CASCADE`.
- If discussion messages are stored in a dedicated research message table, the
  discussion-message foreign key must point there. If they are stored in
  `chat_messages`, the foreign key must point to `chat_messages(id)`.
- Paper passage links store `paper_id`, `page_number` when available, and the
  selected text preview.
- Paper region links store `paper_id`, `page_number`, `x`, `y`, `width`, and
  `height`.
- Code path links store repository-relative path plus optional line number.
- Code path links must be resolved server-side against an allowlisted project
  root. Reject absolute paths, `..`, home-directory expansion, and paths outside
  the configured root before any file content can be read or sent to an LLM.
- `relation` is required because link direction is evidence semantics, not only
  connectivity. A link that supports a hypothesis is different from one that
  contradicts it.

### `research_questions`

Fields:

- `id`
- `project_id`
- `question`
- `status`: `open`, `investigating`, `answered`, `abandoned`
- `current_answer`
- `created_at`
- `updated_at`

Reason: project-level `current_state` is too broad for day-to-day progress.
Research questions make "what are we trying to learn?" queryable and exportable.

### `experiment_runs`

Fields:

- `id`
- `project_id`
- `title`
- `status`: `planned`, `running`, `succeeded`, `failed`, `inconclusive`
- `hypothesis`
- `method`
- `config_json`
- `metrics_json`
- `artifact_paths_json`
- `log_excerpt`
- `conclusion`
- `created_at`
- `updated_at`

### `research_discussions`

Fields:

- `id`
- `project_id`
- `title`
- `instructions`
- `grounding_snapshot_json`
- `created_at`
- `updated_at`

`grounding_snapshot_json` is a frozen snapshot of the selected context at the
time the discussion is created. This avoids a stale "live context pack" problem:
later edits to notes or experiment runs must not silently change the evidence
used for an older LLM answer.

Example:

```json
[
  {"type": "paper", "paper_id": 3},
  {"type": "paper_passage", "paper_id": 3, "page": 2, "quote": "..."},
  {"type": "research_note", "note_id": 8},
  {"type": "code_path", "path": "app/services.py", "line": 880},
  {"type": "experiment_run", "experiment_run_id": 4}
]
```

Implementation note: a context picker UI can exist, but `ContextPack` should not
be the core domain entity in the first implementation. The durable record is the
discussion's grounding snapshot.

### `research_messages`

Fields:

- `id`
- `discussion_id`
- `role`: `user`, `assistant`, `system`
- `content`
- `metadata_json`
- `source_ids_json`
- `grounding_status`: `grounded`, `ungrounded`, `partial`
- `created_at`

Reason: the existing `chat_sessions.paper_id` is `NOT NULL`, so research
discussions should not initially reuse `chat_sessions`. A dedicated table avoids
a SQLite table rebuild and preserves a cleaner contract.

## API Plan

### Project APIs

- `POST /api/research/projects`
- `GET /api/research/projects`
- `GET /api/research/projects/{project_id}`
- `PATCH /api/research/projects/{project_id}`
- `GET /api/research/projects/{project_id}/export.md`

Projects and notes use soft deletion through `status=archived`. The UI should
not expose hard delete while linked notes, paper evidence, or discussion
messages exist.

### Note APIs

- `POST /api/research/notes`
- `GET /api/research/notes`
  - Query: `project_id`, `q`, `tag`, `status`, `note_type`
- `GET /api/research/notes/{note_id}`
- `PATCH /api/research/notes/{note_id}`
- `POST /api/research/notes/{note_id}/links`
- `GET /api/research/notes/{note_id}/links`

Search can start with simple filtering, but PR E should introduce SQLite FTS5
for `title` and `body_markdown` before the app claims scalable note search.

### Research Question APIs

- `POST /api/research/questions`
- `GET /api/research/questions`
  - Query: `project_id`, `status`
- `PATCH /api/research/questions/{question_id}`

### Paper-To-Research APIs

- `POST /api/papers/{paper_id}/research-notes`
  - Creates a note from selected passage, selected region, or Ask Paper answer.
- `POST /api/chat/messages/{message_id}/research-note`
  - Captures an LLM answer into a note with a back-reference to the source
    message.

### Experiment APIs

- `POST /api/research/experiments`
- `GET /api/research/experiments`
- `GET /api/research/experiments/{experiment_run_id}`
- `PATCH /api/research/experiments/{experiment_run_id}`

### Grounding Snapshot And Discussion APIs

- `POST /api/research/discussions`
- `GET /api/research/discussions/{session_id}`
- `POST /api/research/discussions/{session_id}/messages`

The request that creates a discussion includes selected context items. The
server validates every item, resolves safe code and artifact paths, and stores
the validated result in `grounding_snapshot_json`.

Do not reuse the existing `chat_sessions` table for research discussions unless
the schema is first migrated. Current `chat_sessions.paper_id` is `NOT NULL`,
which does not fit project-level discussions.

## UX Plan

### New Top-Level Area: Research

Add a `Research` view beside the paper reader workflow.

Primary layout:

- left: project list and note filters
- center: note editor or discussion thread
- right: context/evidence panel

### Paper Reader Integration

In the paper reader, add actions:

- Save selected passage to note
- Save selected region to note
- Send selected passage to research discussion
- Add paper to project
- Add Ask Paper answer to note

### Research Discussion Flow

The user creates a grounding snapshot by selecting:

- research project
- notes
- papers
- passages or page regions
- code paths
- experiment runs
- custom instruction/system prompt

The LLM receives a structured prompt:

1. research goal
2. current state
3. selected notes
4. selected papers/passages
5. selected code references
6. selected experiment summaries
7. user question

The answer is saved as a discussion message. The user can then promote the
answer to a research note or link it to a paper.

## Implementation Phases

### PR A: Local PDF Upload

Reason: it is the next missing input path and is already requested.

Deliverables:

- `POST /api/papers/upload`
- PDF upload UI in the import bar
- Use existing PDF extraction and page rendering pipeline
- Fallback title from filename when metadata is unavailable
- Tests for upload route and service ingestion

Exit criteria:

- A local PDF can be uploaded and read as selectable pages.
- Ask Paper works against the uploaded paper.
- `pytest` and `npm run build` pass.

### PR B: Research Project And Notes MVP

Deliverables:

- `research_projects`, `research_questions`, `research_notes`,
  `research_links` tables
- DB constraints for `research_links` source ownership and foreign keys
- Required `relation` on every research link
- Project list UI
- Markdown note editor
- Paper passage to note action
- Ask Paper answer to note action
- Project Markdown export
- Soft archive for projects and notes

Exit criteria:

- A user can create a project, save a paper passage as a note, edit it, and
  export the project.
- Every note can display its linked paper evidence.
- Project export renders evidence links as readable citations such as
  `[Paper Title, p.3]`, not raw IDs.
- `POST /api/papers/{paper_id}/research-notes` creates both a
  `research_notes` row and a `research_links` row with `link_type=paper_passage`
  when selected text is supplied.
- No UI hard-delete path removes linked projects or notes; archive is used
  instead.

### PR C: Experiment Run Records

Deliverables:

- `experiment_runs` table
- Experiment run CRUD APIs
- UI for status, hypothesis, config JSON, metrics JSON, conclusion, and artifact
  paths
- Link experiment runs to notes and projects

Exit criteria:

- A user can record an experiment result and link it to a note.
- Experiment metrics can be included in project export.

### PR D: Research Discussion With Grounding Snapshots

Deliverables:

- `research_discussions` and `research_messages` tables
- UI context picker for papers, passages, notes, code paths, and experiment runs
- Research discussion API using Codex answer mode first
- Prompt builder with explicit source sections
- Save LLM answer to note
- Server-side validation for every grounding item, especially `code_path` and
  experiment artifact paths

Exit criteria:

- A user can ask Codex a project-level question grounded in selected papers,
  notes, code references, and experiment results.
- The answer is stored and can be promoted to a note with source links.
- Every saved assistant message either includes at least one verifiable
  `source_id` in `source_ids_json` or is explicitly flagged
  `grounding_status=ungrounded`.
- Context preview shows exactly which notes, passages, code paths, and
  experiment summaries will be sent before the LLM call.

### PR E: Search And Review Layer

Deliverables:

- Search across papers, notes, discussions, and experiment titles
- Research status dashboard
- Open questions list
- Decisions list
- Stale note and stale experiment detection

Exit criteria:

- A user can answer "what is the current status of this research project?"
  from the workspace without manually scanning all notes.

## Prompt Contract For Research Discussion

The research prompt should not hide sources inside prose. Use explicit sections:

```text
You are discussing a research project inside Open AlphaXiv Local.

Constraints:
- Use only the provided project notes, paper passages, code references, and
  experiment summaries.
- Distinguish evidence from hypothesis.
- If an experiment result is inconclusive, say so.
- Mention source IDs when making claims.
- If no source supports a claim, label it as a hypothesis.
- Do not modify files or run shell commands unless the user explicitly requests
  an implementation task.

Project:
...

Current state:
...

Notes:
...

Paper evidence:
...

Code references:
...

Experiment evidence:
...

Question:
...
```

Every prompt item must have a stable source ID. Example source IDs:

- `paper:3`
- `paper_passage:3:page=2:link=17`
- `note:8`
- `code:app/services.py:880`
- `experiment:4`

The saved assistant message must store the source IDs it actually used, or be
marked `grounding_status=ungrounded`.

## Acceptance Criteria

The Research Workspace is useful when:

- A user can reconstruct why a research direction changed.
- LLM answers remain linked to their source context.
- Paper evidence, experiment evidence, and code evidence can be reviewed
  separately.
- Notes are editable after model output is generated.
- Exported Markdown is readable without running the app.
- No secrets, private keys, or unrelated local files are included in context
  packs by default.

## Risks And Controls

| Risk | Level | Control |
| --- | --- | --- |
| Plain notes become unstructured and untraceable. | High | Make source links first-class from PR B. |
| Context packs silently include too much code or data. | High | Require explicit user-selected paths and show a preview before sending. |
| LLM output is treated as evidence. | High | Store model answers as discussion messages; promote to notes only by user action. |
| Polymorphic evidence links become orphaned. | High | Add DB `CHECK` constraints, explicit FK where possible, and service-layer validation for typed targets. |
| Code or experiment paths leak secrets. | High | Resolve every path under an allowlisted root and reject absolute/out-of-root paths before reading content. |
| Live context changes invalidate old discussion history. | High | Store frozen `grounding_snapshot_json` on each research discussion. |
| Experiment metrics are misleading due to inconsistent schemas. | Medium | Store metrics as JSON first, then add schema templates after real usage patterns emerge. |
| Research UI becomes too complex too early. | Medium | Ship project + note + links before context packs. |
| Paper upload metadata quality is weak. | Medium | Use filename/title fallback and allow user edits. |

## Immediate Next Step

Implement PR A: Local PDF Upload. It unblocks the rest of the research workflow
because the workspace must accept both arXiv papers and local papers before
research projects can be comprehensive.

After PR A, implement PR B: Research Project And Notes MVP.

## Claude Review Summary

Claude review was run in three smaller segments after full-plan prompts timed
out. The accepted review changes are:

- Replace first-class `ContextPack` with frozen
  `ResearchDiscussion.grounding_snapshot_json`.
- Do not reuse `chat_sessions` for research discussion until its `paper_id NOT
  NULL` constraint is migrated; use dedicated research discussion tables first.
- Add `ResearchQuestion` so progress/status is structured instead of only
  project prose.
- Add `EvidenceLink.relation` so links can mean `supports`, `contradicts`,
  `extends`, `implements`, `cites`, `mentions`, or `questions`.
- Enforce `research_links` ownership with SQLite `CHECK` constraints and FKs.
- Validate `code_path` and experiment artifact paths server-side before any LLM
  prompt construction.
- Add explicit PR B and PR D tests for note-from-passage and grounded source
  IDs.

Raw review outputs:

- `/tmp/research_workspace_claude_segment1.out`
- `/tmp/research_workspace_claude_segment2.out`
- `/tmp/research_workspace_claude_segment3.out`
