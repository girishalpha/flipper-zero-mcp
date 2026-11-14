"""Persistent, PC-side task-knowledge base (the repo's memory of past tasks).

Notes live as Markdown files under the repo's `knowledge/` folder - one file per
topic. They are per-user local memory (git-ignored), so an agent can record what
was non-obvious about a task and reuse it next time instead of rediscovering it.

This module is the pure helper layer; `tools/knowledge.py` wraps these functions
as MCP tools. File format of `knowledge/<slug>.md`:

    # <topic>

    ## 2026-11-14 15:04
    <freeform notes: gotchas, the working sequence, device quirks, dead-ends>

    ## 2026-11-14 16:20
    <a later appended entry>
"""

import os
import re
import time

# knowledge/ sits at the repo root, one level above this package.
KB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")


def slug(s: str) -> str:
    """Normalise a topic/title into a safe filename stem."""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "note"


def _note_path(topic: str) -> str:
    return os.path.join(KB_DIR, slug(topic) + ".md")


def list_notes() -> str:
    """One line per saved note: '<slug> : <title>'."""
    if not os.path.isdir(KB_DIR):
        return "no knowledge yet - save learnings with flipper_kb_save"
    out = []
    for fn in sorted(os.listdir(KB_DIR)):
        if not fn.endswith(".md"):
            continue
        first = ""
        try:
            with open(os.path.join(KB_DIR, fn), encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        first = line.strip().lstrip("# ")
                        break
        except Exception:
            pass
        out.append("- %s : %s" % (fn[:-3], first))
    return "\n".join(out) or "no knowledge yet"


def read_note(topic: str) -> str:
    """Return a note's full Markdown, or a hint if it does not exist."""
    p = _note_path(topic)
    if not os.path.isfile(p):
        return f"no note '{slug(topic)}' - flipper_kb_list to see topics"
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def search_notes(query: str) -> str:
    """Grep every note for `query`; returns 'slug:line: text' matches."""
    if not os.path.isdir(KB_DIR):
        return "no knowledge yet"
    q = query.lower()
    hits = []
    for fn in sorted(os.listdir(KB_DIR)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(KB_DIR, fn), encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if q in line.lower():
                    hits.append("%s:%d: %s" % (fn[:-3], i, line.strip()))
    return "\n".join(hits[:60]) or f"no matches for {query!r}"


def save_note(topic: str, content: str, append: bool = True) -> str:
    """Record a learning under `knowledge/<slug>.md`.

    append=True adds a timestamped section to the topic; append=False replaces it.
    """
    os.makedirs(KB_DIR, exist_ok=True)
    p = _note_path(topic)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    if append and os.path.isfile(p):
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(f"\n\n## {stamp}\n{content}\n")
    else:
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(f"# {topic}\n\n## {stamp}\n{content}\n")
    return f"saved -> knowledge/{slug(topic)}.md"
