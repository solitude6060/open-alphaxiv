# PR #8 Review Notes: Blocked Claude Lane And Local Finding

## Scope

PR #8: `feature/research-discussions` into `feature/experiment-runs`

Reviewed feature:

- research discussions
- discussion messages
- grounding snapshots
- project export sections
- lightweight Research panel UI

## External Review Attempts

Claude was attempted in segmented mode to reduce context size.

| Segment | Prompt | Output | Result |
| --- | --- | --- | --- |
| services/store | `/tmp/pr8_review_services_prompt.txt` | `/tmp/pr8_review_services_claude.out` | timed out after 180s, 0-byte output |
| CLI ping | inline `Return exactly: ok` | `/tmp/claude_ping.out` | succeeded, output `ok` |
| store embedded diff | `/tmp/pr8_review_store_embedded_prompt.txt` | `/tmp/pr8_review_store_claude.out` | timed out after 60s, 0-byte output |

Conclusion: Claude CLI authentication and basic execution worked, but review
prompts did not produce usable output in this environment.

## Local Review Finding

### Missing foreign keys for discussion-message references

Severity: major

Files:

- `app/store.py`
- `tests/test_services.py`

Failure mode:

`grounding_snapshots.discussion_message_id` and
`research_links.discussion_message_id` were stored as plain integers while
SQLite foreign keys are enabled. Deleting a discussion message could leave
message-owned research links orphaned and grounding snapshots pointing at a
missing message.

Fix:

- `research_links.discussion_message_id` now references
  `research_discussion_messages(id)` with `ON DELETE CASCADE`.
- `grounding_snapshots.discussion_message_id` now references
  `research_discussion_messages(id)` with `ON DELETE SET NULL`, preserving the
  immutable snapshot content while removing the stale pointer.
- Added `test_discussion_message_references_follow_message_lifecycle`.

## Verification

- Targeted regression:
  `env PYTHONPATH=.:.deps python3 -m pytest tests/test_services.py::test_discussion_message_references_follow_message_lifecycle`
  -> passed
