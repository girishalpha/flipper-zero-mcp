"""Flipper Zero MCP server - drive a Flipper Zero from Claude Code agents.

Public surface:
    from flipper_mcp import mcp, main
"""

from .app import mcp
from .server import main

__version__ = "0.2.0"
__all__ = ["mcp", "main", "__version__"]
