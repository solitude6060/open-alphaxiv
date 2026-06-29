# PR Review 2026-06-29 PR3 Fix Log

PR: https://github.com/solitude6060/open-alphaxiv/pull/3

## Summary

Triple review used OpenCode DeepSeek, Claude, and Codex self-review. OpenCode
approved. Claude and Codex requested changes. A Codex Spark fallback was also
captured as supplementary review evidence. This log records verified findings,
fixes, and validation.

## Fixes

| Finding | Fix | Tests |
|---|---|---|
| Markdown renderer can loop on malformed block starts. | Paragraph fallback now consumes the current line before scanning continuation lines. | `npm run build`; browser check of Markdown answer rendering. |
| Lazy page text-layer extraction can block the event loop. | Page text-layer endpoints now offload service work through `asyncio.to_thread()`. | `tests/test_api.py::test_paper_full_text_and_page_manifest_over_http` |
| Per-page text-layer fanout and duplicate extraction. | Added `GET /api/papers/{paper_id}/pages/text` and a per-paper single-flight lock for text-layer artifact generation. The frontend loads all text layers in one request. | `tests/test_services.py::test_page_text_layers_lazy_generation_is_idempotent` |
| Invalid page text requests did not reliably return 404. | `paper_page_text_layer()` validates that the requested page image exists before returning text. | `tests/test_services.py::test_page_text_layer_rejects_unknown_page`; API 404 assertion. |
| PDF-unavailable state removed all reading content. | Added an abstract fallback in the reader empty state. | `npm run build` |
| Ask Paper was single-turn only. | Added persistent chat-session list/read APIs, frontend conversation state, and session-aware message posting. | `tests/test_api.py::test_chat_session_history_over_http`; `tests/test_services.py::test_chat_session_persists_conversation_messages` |
| Codex follow-ups lacked conversation history and explicit whole-paper scope. | Codex prompts now include recent conversation history, paper file references, and `whole_paper` scope when no passage or image selection is supplied. | `tests/test_services.py::test_codex_answer_receives_history_and_whole_paper_scope` |

## Verification

- `env PYTHONPATH=.:.deps python3 -m pytest tests/test_api.py::test_chat_session_history_over_http tests/test_services.py::test_chat_session_persists_conversation_messages tests/test_services.py::test_codex_answer_receives_history_and_whole_paper_scope tests/test_services.py::test_chat_session_rejects_different_paper -vv` -> 4 passed.
- `env PYTHONPATH=.:.deps python3 -m pytest` -> 27 passed.
- `npm run build` -> passed.
- Minimal ASGI reproduction for `POST /api/chat/sessions` and `POST /api/chat/sessions/{session_id}/messages` -> both returned HTTP 200 after converting new session routes to `async + to_thread`.

## Deferred

- Italic inline Markdown remains unsupported by the lightweight frontend
  renderer.
- The rejected Y-coordinate finding remains documented here; current Poppler
  bounding boxes render correctly with the top-origin mapping verified in the
  browser.
