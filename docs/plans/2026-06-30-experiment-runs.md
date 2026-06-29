# Experiment Runs MVP Plan

## Goal

Add the first structured experiment tracking layer for research projects:
experiment runs, experiment artifacts, metrics, status transitions, note
capture, evidence links, and project Markdown export.

This PR is stacked on PR #6 because it depends on `research_projects`,
`research_notes`, and `research_links`.

## First-Principles Check

The user need is not a free-form note for experiment text. A useful experiment
record must preserve:

- what hypothesis the run was testing
- which dataset, code reference, command, and parameters produced the result
- which metrics and output artifacts were produced
- how the run links back into research notes and later LLM discussions

Therefore the minimum PR C object model is:

- `experiment_runs`
- `experiment_artifacts`

`research_links` remains the evidence boundary. Experiment runs and artifacts
must be link targets, not prose-only content embedded in a note.

## Scope

In this PR:

- Add SQLite tables for experiment runs and experiment artifacts.
- Add service and API methods for create/list/get/update/archive workflows.
- Add artifact attachment under an experiment run.
- Add experiment run to research note capture.
- Validate experiment link targets in `research_links`.
- Include experiment runs and artifacts in research project Markdown export.
- Add a lightweight Experiments section to the Research UI panel.

Out of scope:

- Project-level LLM discussions.
- Frozen grounding snapshots.
- Global full-text search.
- Automatic codebase ingestion.
- Uploading artifact files; this PR stores local/remote artifact references.
- Multi-user permissions.

## API Contract

Experiment runs:

- `POST /api/experiments/runs`
- `GET /api/experiments/runs`
- `GET /api/experiments/runs/{run_id}`
- `PATCH /api/experiments/runs/{run_id}`
- `POST /api/experiments/runs/{run_id}/research-note`

Experiment artifacts:

- `POST /api/experiments/runs/{run_id}/artifacts`
- `GET /api/experiments/runs/{run_id}/artifacts`

## Tests First

Service tests:

- Create a run under a project with hypothesis, dataset, command, code
  reference, parameters, and metrics.
- Update run status and completed timestamp.
- Attach an artifact with type, URI, label, and metadata.
- Capture a run into a research note and verify a `research_links` row with
  `link_type=experiment_run`.
- Link a note to an experiment artifact and verify target validation.
- Export a project and verify experiment runs, metrics, artifacts, and
  citations are readable.

API tests:

- Exercise create/update/list/get run through HTTP.
- Exercise artifact create/list through HTTP.
- Exercise run-to-note capture through HTTP.
- Verify unknown project/run/artifact IDs return 404 or 400 according to the
  target validation path.

Frontend verification:

- `npm run build` must pass.
- The Research panel must show experiment runs without breaking project notes,
  paper tags, or provider list.

## Acceptance Criteria

- A user can record an experiment run under a research project.
- A user can record run metadata: hypothesis, dataset, code reference, command,
  parameters, metrics, summary, and status.
- A user can attach artifact references to a run.
- A user can capture a run into a Markdown research note.
- Experiment runs and artifacts can be cited through `research_links`.
- Project export includes experiment runs, metrics, artifacts, and evidence.
- No UI hard-delete path removes experiment records.
