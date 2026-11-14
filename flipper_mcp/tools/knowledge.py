"""Task-knowledge tools: the repo's memory of past tasks.

Thin MCP wrappers over `flipper_mcp.knowledge_base`; all the file handling lives
in that helper module. Check these at the start of a task to reuse prior work,
and save what you learned at the end.
"""

from .. import knowledge_base as kb
from ..app import mcp


@mcp.tool()
def flipper_kb_list() -> str:
    """List saved task-knowledge notes (the repo's memory of past tasks). Each
    note is a topic the agent learned; read one with flipper_kb_read. Check this
    at the start of a task to reuse prior work instead of starting from scratch."""
    return kb.list_notes()


@mcp.tool()
def flipper_kb_read(topic: str) -> str:
    """Read a saved task-knowledge note by topic (slug or title)."""
    return kb.read_note(topic)


@mcp.tool()
def flipper_kb_search(query: str) -> str:
    """Search all task-knowledge notes for a term; returns matching notes+lines.
    Run at the START of a task to find what was already learned about it."""
    return kb.search_notes(query)


@mcp.tool()
def flipper_kb_save(topic: str, content: str, append: bool = True) -> str:
    """Record a learning for future tasks, under the repo's knowledge/ folder,
    keyed by topic. append=True adds a timestamped entry to the topic;
    append=False replaces it. Save what was NON-OBVIOUS: gotchas, the working
    sequence, device quirks, dead-ends - so similar future tasks reuse it instead
    of rediscovering. Do this at the end of any task that taught you something."""
    return kb.save_note(topic, content, append)
