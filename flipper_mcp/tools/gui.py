"""GUI tools: button presses, menu navigation, unlock, screenshot.

These are the eyes-and-hands of the agent: `flipper_press`/`flipper_navigate`
drive the menus, `flipper_screenshot` shows the result. The shared `_with_screen`
helper lets an action optionally return the resulting screen in the same call.
"""

import time

from mcp.server.fastmcp import Image

from ..app import mcp
from ..imaging import frame_png
from ..transport import Flipper

VALID_KEYS = {"up", "down", "left", "right", "ok", "back"}


def _with_screen(f: Flipper, text: str):
    """Return [text, screenshot] for tools that report the screen after acting."""
    time.sleep(0.3)  # let the GUI redraw
    try:
        data, orientation = f.screen_frame()
    except (RuntimeError, TimeoutError) as e:
        return f"{text} (screenshot failed: {e})"
    return [text, Image(data=frame_png(data, flipped=orientation == 1), format="png")]


@mcp.tool()
def flipper_press(button: str, kind: str = "short", screenshot: bool = False):
    """Send one button press. button: up/down/left/right/ok/back. kind: short/long/press/release.
    With screenshot=True the screen after the press is returned too."""
    with Flipper() as f:
        out = f.cli(f"input send {button.lower()} {kind.lower()}") or f"sent {button} {kind}"
        return _with_screen(f, out) if screenshot else out


@mcp.tool()
def flipper_navigate(keys: str, delay_ms: int = 250, screenshot: bool = False):
    """Send a sequence of button presses to navigate menus. keys is comma- or
    space-separated, e.g. 'down,down,ok' or 'back back up ok'. Valid keys:
    up/down/left/right/ok/back; append ':long' for a long press, e.g. 'ok:long'.
    A short pause runs between presses. With screenshot=True the screen after
    the last press is returned too, so one call both acts and shows the result."""
    seq = [k.strip().lower() for k in keys.replace(",", " ").split() if k.strip()]
    bad = [k for k in seq if k.split(":")[0] not in VALID_KEYS or k.split(":")[1:] not in ([], ["long"], ["short"])]
    if bad:
        return f"invalid keys: {bad}"
    with Flipper() as f:
        for k in seq:
            key, _, kind = k.partition(":")
            f.cli(f"input send {key} {kind or 'short'}")
            time.sleep(max(0, delay_ms) / 1000)
        out = f"sent {len(seq)} presses: {' '.join(seq)}"
        return _with_screen(f, out) if screenshot else out


@mcp.tool()
def flipper_unlock():
    """Unlock a keypad-locked Flipper (Back x3) and return the screen. While
    locked, screenshots are refused. A PIN lock cannot be cleared this way:
    enter the PIN on the device, or with flipper_navigate."""
    with Flipper() as f:
        for _ in range(3):
            f.cli("input send back short")
            time.sleep(0.05)
        return _with_screen(f, "sent Back x3")


@mcp.tool()
def flipper_screenshot(save_path: str = "") -> Image:
    """Capture the Flipper's current screen (128x64, upscaled 4x) as a PNG so you
    can see what a press/navigate did. Optionally also save it to save_path on the PC."""
    with Flipper() as f:
        data, orientation = f.screen_frame()
    png = frame_png(data, flipped=orientation == 1)
    if save_path:
        with open(save_path, "wb") as fh:
            fh.write(png)
    return Image(data=png, format="png")
