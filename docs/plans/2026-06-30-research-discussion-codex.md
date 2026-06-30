# Research Discussion Codex Plan

## Goal

Connect project-level research discussions to the local Codex CLI so a research
project can behave like a conversational research assistant grounded in durable
project state, notes, evidence links, experiment runs, discussion history, and a
frozen grounding snapshot.

## Survey

Current implementation:

- Paper chat already supports `answer_mode="codex"` through `codex exec`.
- Paper Codex prompts are paper-specific: paper metadata, selected passage,
  selected image region, full paper text, paper file references, and paper chat
  history.
- Research discussions already store `research_discussions` and
  `research_discussion_messages`.
- Grounding snapshots already freeze project state, questions, notes, evidence
  links, experiment runs, and artifacts.
- Research UI can create discussions, save manual messages, and create
  grounding snapshots, but it cannot ask Codex or store generated assistant
  messages.

## First-Principles Audit

### 1. What is the user's actual need?

The need is not another free-text note box. The user needs a research assistant
that can discuss a project using durable research state and then preserve both
the question and generated answer in the project history.

### 2. What assumption is making this approach attractive?

The inherited assumption is that paper-level Codex chat can be reused directly
for research-level discussion.

### 3. Is that assumption verified for this case?

Partially. The Codex execution boundary can be reused, but the prompt contract
cannot. Paper chat is grounded in one paper; research discussion must be
grounded in a project snapshot, research notes, experiment runs, and discussion
history.

### 4. If the assumption were wrong, what changes?

If paper-level prompt reuse were wrong, the fix is a separate research prompt
builder and service workflow while sharing only the low-level Codex CLI runner.

### 5. Does this address the underlying need?

Yes. A Codex-backed discussion turn must create a user message, freeze the
grounding context, call Codex, store the assistant message, and record metadata
that makes the answer auditable later.

## Scope

In this PR:

- Add a research-discussion Codex prompt builder.
- Add a service workflow for a full Codex discussion turn:
  - validate discussion and project
  - create the user discussion message
  - create a grounding snapshot tied to that user message
  - call local `codex exec`
  - store the assistant discussion message with Codex metadata
- Add an HTTP endpoint for the discussion Codex turn.
- Add Research panel UI controls to ask Codex from a selected discussion.
- Add tests for prompt content, persistence, metadata, disabled Codex handling,
  and HTTP behavior.

Out of scope:

- Browser-triggered `codex login`.
- Background job queue for long-running Codex calls.
- Vector search or automatic codebase indexing.
- Multi-user permissions.
- Remote model providers other than the existing local Codex CLI boundary.

## API Contract

`POST /api/research/discussions/{discussion_id}/codex`

Request:

```json
{
  "content": "What should I try next?",
  "system_prompt": "Answer in Traditional Chinese with Markdown bullets."
}
```

Response:

```json
{
  "discussion_id": 1,
  "user_message": { "...": "..." },
  "assistant_message": { "...": "..." },
  "grounding_snapshot": { "...": "..." },
  "answer": "..."
}
```

## Tests First

Service tests:

- Codex discussion turn stores user and assistant messages.
- Prompt includes project state, notes, evidence, experiment runs, discussion
  history, grounding snapshot content, and user system prompt.
- Assistant metadata includes provider/model, user message ID, grounding
  snapshot ID, prompt/context sizes, and Codex runtime metadata.
- Disabled Codex raises a clear error.

API tests:

- HTTP endpoint creates a Codex discussion turn and returns persisted messages.
- Disabled/unavailable Codex maps to 400/500 using existing error conventions.

Frontend verification:

- `npm run build` must pass.
- Research panel lets the user ask Codex from the selected discussion.
- The UI refreshes discussion counts and shows status/errors consistently.

## Acceptance Criteria

- A researcher can send a project-level discussion question to Codex.
- The backend sends a research-specific grounded prompt, not a paper-chat prompt.
- The answer is stored as a durable assistant discussion message.
- A grounding snapshot is created for the user question.
- The feature uses the existing local Codex CLI settings and availability
  checks.
- Full backend tests and frontend build pass.
