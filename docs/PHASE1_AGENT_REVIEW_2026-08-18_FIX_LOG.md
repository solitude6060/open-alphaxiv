# Phase 1 agent-runtime review fix log

Date: 2026-08-18
Review: `docs/PHASE1_AGENT_REVIEW_2026-08-18.md`

| ID | Repro | Fix | Tests | Files |
| --- | --- | --- | --- | --- |
| P1-1 | `tests/test_mcp.py::test_mcp_http_offloads_handler_off_event_loop` failed because `app.main.to_thread` was never called from `POST /mcp`. | `payload = await to_thread(handle_mcp_request, body, service())`. | Same test now passes. HTTP list-tools still passes via the existing `to_thread` stub. | `app/main.py`, `tests/test_mcp.py` |
| P1-2 | First reviewer read a local `search_arxiv` that called `app.services.fetch_text`. Current tree: `from ..connectors.arxiv import search_arxiv`. | MCP tool is the connector function, which waits on `ARXIV_LIMITER` inside `fetch_text`. | `tests/test_mcp.py::test_mcp_search_arxiv_is_the_rate_limited_connector` asserts the two names are the same object. Limiter sleep is covered in `tests/test_connectors.py`. | `app/mcp/tools.py`, `app/connectors/arxiv.py`, `tests/test_mcp.py` |
