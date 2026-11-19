"""The shared FastMCP instance.

This lives in its own tiny module so both `server` and every `tools.*` module
can `from flipper_mcp.app import mcp` without creating an import cycle: nothing
here imports from the rest of the package.
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP("flipper")


def _hints(read_only: bool, destructive: bool, idempotent: bool, open_world: bool) -> ToolAnnotations:
    """Declare all four MCP hints explicitly so hosts can warn before risky calls."""
    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


# Presets for `@mcp.tool(annotations=...)`. Pick the one that matches what the
# tool actually does; "open world" means it touches the radio, a host PC, or
# arbitrary on-device code rather than only the Flipper's own state.
READ_ONLY = _hints(True, False, True, False)           # reads device/PC state, changes nothing
ADDITIVE = _hints(False, False, True, False)          # creates/sets something, repeat is harmless
OVERWRITE = _hints(False, True, True, False)          # replaces or deletes data, repeat is harmless
ACTION = _hints(False, False, False, False)           # drives the device (buttons, launch app)
DESTRUCTIVE = _hints(False, True, False, False)       # interrupts state or appends/replaces notes
EXTERNAL = _hints(False, False, False, True)          # radio receive/transmit
EXTERNAL_DESTRUCTIVE = _hints(False, True, False, True)  # arbitrary CLI/JS, keystroke injection
