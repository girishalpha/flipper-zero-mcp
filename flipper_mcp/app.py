"""The shared FastMCP instance.

This lives in its own tiny module so both `server` and every `tools.*` module
can `from flipper_mcp.app import mcp` without creating an import cycle: nothing
here imports from the rest of the package.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("flipper")
