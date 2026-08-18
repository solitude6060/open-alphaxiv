# Phase 2 discovery-graph review fix log

Date: 2026-08-18
Review: `docs/PHASE2_GRAPH_REVIEW_2026-08-18.md`

| ID | Repro | Fix | Tests | Files |
| --- | --- | --- | --- | --- |
| P2-1 | Insert `mvp1-local` `Prior work 1: …` rows after ingest. GET `/literature-graph` returned them as `status=ok` with `Data from Semantic Scholar`. Failed S2 build left them in place. | Delete `mvp1-local` nodes/edges on `Store.init_db` and on each graph read. GET without a successful `literature_builds` row returns empty nodes and no S2 attribution. A later S2 failure keeps prior `semantic_scholar` nodes. | `test_literature_graph_hides_leftover_mvp1_local_nodes`; `test_failed_s2_build_does_not_keep_mvp1_local_nodes`; `test_failed_rebuild_keeps_previous_semantic_scholar_nodes` | `app/store.py`, `app/services.py`, `tests/test_services.py` |
