# Task knowledge base

Persistent memory for Flipper tasks. Each `.md` here is a **topic** — what was
learned doing a task (gotchas, the working sequence, device quirks, dead-ends) so
a similar future task reuses it instead of starting from scratch.

Managed by the MCP tools (no manual editing needed):
- `flipper_kb_list` — see all topics.
- `flipper_kb_search "<term>"` — find prior learnings. **Run at the start of a task.**
- `flipper_kb_read "<topic>"` — read a note.
- `flipper_kb_save "<topic>" "<content>"` — record a learning. **Run at the end of a task.**

Suggested workflow for any task:
1. `flipper_index` + `flipper_kb_search` the task topic — get oriented.
2. Do the work.
3. `flipper_kb_save` the non-obvious bits for next time.
