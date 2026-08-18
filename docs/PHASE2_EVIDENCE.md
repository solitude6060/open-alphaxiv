# Phase 2 evidence

Recorded: 2026-08-18 on this machine.
Branch: `feature/phase1-agent-runtime` working tree (Phase 1 + Phase 2,
uncommitted).

This file contains command output from this session. It does not contain
API keys.

## Automated tests

Command:

```bash
env PYTHONPATH=.:.deps python3 -m pytest -q --tb=line
```

Result:

```text
98 passed in 6.85s
pytest_exit:0
```

CI uses fixtures and monkeypatches except where noted below.

## Web production build

Command: `cd web && npm run build`

```text
vite v8.1.0 building client environment for production...
✓ 50 modules transformed.
dist/index.html                   0.40 kB │ gzip:  0.27 kB
dist/assets/index-Diu2Nb3E.css   21.03 kB │ gzip:  4.79 kB
dist/assets/index-Dinsqvhg.js   238.97 kB │ gzip: 73.24 kB
✓ built in 109ms
```

## Docker Compose file

Command: `docker compose config -q`

```text
compose_config_exit:0
```

Images were not built in this pass.

## Live arXiv feed

Command:

```bash
env PYTHONPATH=.:.deps python3 scripts/live_phase2_check.py
```

First run (feed portion; Semantic Scholar returned 429):

```text
feed_category: cs.LG
feed_item_count: 25
feed_skipped: false
feed_landing_hosts: ["arxiv.org"]
pdf_files_on_disk: []
feed_sample_titles:
- Decoding the Past: An Uncertainty-Aware Deep Learning Framework for Sex Attribution in Prehistoric Hand Stencils
- Split the Labor: Separating Evidence Interpretation from Decision Aggregation
- RecipeNet: A Hierarchical Transformer for Recipe Data
- Universal Thermodynamic Interatomic Potentials for Crystalline Materials
- Rollplex: Cross-Phase GPU Spatial Sharing for Vision Language Model Post-Training
```

The feed path met the Phase 2 exit bar of ≥ 10 real `cs.LG` rows with
`arxiv.org` landing URLs and no PDF bytes written.

## Live Semantic Scholar graph

Same command, plus a later isolated `fetch_paper_neighborhood('1706.03762')`
after a 20-second wait. No `SEMANTIC_SCHOLAR_API_KEY` was set.

```text
graph_status: error
graph_node_count: 0
graph_attribution: ""
has_prior_work_placeholder: false
semantic_scholar_api_key_present: false
graph_status_reason: Client error '429 ' for url
  'https://api.semanticscholar.org/graph/v1/paper/ARXIV:1706.03762?fields=...'
```

The isolated retry after 20 seconds also returned HTTP 429. The failed
build stored no literature nodes and did not invent `Prior work N` titles.

`request_s2_json` now retries once on 429 and, after exhaustion, tells the
operator to set `SEMANTIC_SCHOLAR_API_KEY`.

## Still open

- Live graph build with a Semantic Scholar API key.
- Cursor MCP tool listing from the Cursor agent UI.
- `docker compose up --build` of the production web image.
- Live `codex exec` paper Q&A: ran; host usage limit until 2026-08-20 13:52.
  Claude and OpenCode paper Q&A are in `docs/PHASE1_EVIDENCE.md`.

## Deferred from the Phase 2 recreation sketch

Bibliographic coupling Jaccard, co-citation Jaccard, and abstract cosine
ranking were not implemented. v1 scoring is direct cite / cited-by with
score `1.0`.
