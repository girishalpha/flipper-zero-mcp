"""Flipper Zero MCP server entry point.

Imports every tool module (which registers the tools on the shared FastMCP
instance) and exposes `main()` to run the server or a quick self-test:

    python -m flipper_mcp              # run the MCP server (stdio)
    python -m flipper_mcp --selftest   # open the port, print device + SD info
"""

import sys

from . import tools  # noqa: F401  (import registers every @mcp.tool())
from .app import mcp
from .transport import Flipper


def _selftest():
    with Flipper() as f:
        info = f.cli("device_info", 20)
        print(info.splitlines()[0] if info else "no reply")
        print("storage:", f.cli("storage info /ext", 15).splitlines()[0])
    print("self-test OK")


def main():
    if "--selftest" in sys.argv:
        _selftest()
    else:
        mcp.run()


if __name__ == "__main__":
    main()
