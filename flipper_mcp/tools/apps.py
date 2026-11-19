"""App/loader tools: list running app, open/close built-ins, launch .fap, run JS."""

import time

from ..app import ACTION, EXTERNAL_DESTRUCTIVE, READ_ONLY, mcp
from ..transport import Flipper


@mcp.tool(annotations=READ_ONLY)
def flipper_apps_running() -> str:
    """Show the currently running app (loader info)."""
    with Flipper() as f:
        return f.cli("loader info", 15)


@mcp.tool(annotations=ACTION)
def flipper_loader_open(app: str, args: str = "") -> str:
    """Launch an app by name, optionally with an argument (e.g. a file path).
    Example: flipper_loader_open('Sub-GHz'), or open an app with a saved file."""
    cmd = f'loader open "{app}"' + (f' "{args}"' if args else "")
    with Flipper() as f:
        return f.cli(cmd, 20) or f"opened {app}"


@mcp.tool(annotations=ACTION)
def flipper_loader_close() -> str:
    """Close the currently running app."""
    with Flipper() as f:
        return f.cli("loader close", 15) or "closed"


@mcp.tool(annotations=ACTION)
def flipper_launch_fap(fap_path: str) -> str:
    """Launch an external .fap app by its full SD path, e.g.
    '/ext/apps/GPIO/esp32_wifi_marauder.fap'. External apps are NOT in
    `loader list` (only built-ins are), and launching a GUI app does not return a
    CLI prompt - waiting for one wedges the port. This fires the command and
    returns immediately; follow with flipper_screenshot to see the app, and
    flipper_navigate to drive it. Find paths with flipper_storage_list."""
    with Flipper() as f:
        f.s.write(f'loader open "{fap_path}"\r'.encode())
        time.sleep(2.0)
        f.s.reset_input_buffer()
    return f"launch sent: {fap_path} (use flipper_screenshot to view, flipper_navigate to drive)"


@mcp.tool(annotations=EXTERNAL_DESTRUCTIVE)
def flipper_js_run(script: str, timeout: int = 60) -> str:
    """Run a JavaScript program on the Flipper (mJS engine) and return its output.
    Full on-device automation: gui, gpio, serial, storage, notify, badusb, etc.
    The script is written to /ext/.tmp and executed with the `js` command."""
    path = "/ext/.tmp/mcp_run.js"
    data = script.encode()
    with Flipper() as f:
        f.cli("storage mkdir /ext/.tmp")
        f.write_file(path, data)
        return f.cli(f'js {path}', timeout)
