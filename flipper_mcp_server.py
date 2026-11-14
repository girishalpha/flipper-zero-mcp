"""Backward-compatible launcher for the Flipper Zero MCP server.

The server was refactored from this single file into the `flipper_mcp/` package
(transport, protocol, imaging, knowledge_base, and one tool module per task
domain under `flipper_mcp/tools/`). This shim stays so existing MCP client
configs that point at `flipper_mcp_server.py` keep working untouched.

Prefer launching the package directly in new configs:

    python -m flipper_mcp              # run the server
    python -m flipper_mcp --selftest   # quick device self-test
"""

import os
import sys

# Ensure the repo root (this file's directory) is importable when launched by
# an absolute path, so `import flipper_mcp` resolves to the sibling package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flipper_mcp import mcp  # noqa: E402  (re-exported for any importer of this module)
from flipper_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
