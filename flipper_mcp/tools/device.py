"""Core device tools: info, raw CLI, health check, power, LED/vibro, listen."""

import time

import serial

from ..app import ADDITIVE, DESTRUCTIVE, EXTERNAL, EXTERNAL_DESTRUCTIVE, READ_ONLY, mcp
from ..transport import Flipper, find_port


@mcp.tool(annotations=READ_ONLY)
def flipper_info() -> str:
    """Return the Flipper's device_info (firmware, hardware, radio, battery region)."""
    with Flipper() as f:
        return f.cli("device_info", 20)


@mcp.tool(annotations=EXTERNAL_DESTRUCTIVE)
def flipper_run_cli(command: str, timeout: int = 15) -> str:
    """Run a raw Flipper CLI command and return its output. Full control escape
    hatch: e.g. 'subghz tx_from_file /ext/subghz/foo.sub 433920000', 'nfc',
    'ir tx', 'gpio set pa7 1', 'ps', 'free'. Use flipper_run_cli('help') to list."""
    with Flipper() as f:
        return f.cli(command, timeout)


@mcp.tool(annotations=READ_ONLY)
def flipper_status() -> str:
    """Health check: is the Flipper on USB, is the port free, does the CLI
    answer, which app is running, and can the screen be captured (i.e. is it
    unlocked). Run this first when another tool fails."""
    try:
        port = find_port()
    except RuntimeError as e:
        return f"NOT CONNECTED: {e}"
    try:
        f = Flipper()
    except serial.SerialException as e:
        return (f"PORT BUSY: {port} is present but could not be opened ({e}). Close qFlipper, "
                "lab.flipper.net browser tabs or any other serial tool using it.")
    except RuntimeError as e:
        return f"NO CLI on {port}: {e}"
    with f:
        lines = [f"port: {port}", "cli: OK"]
        wanted = ("hardware_name", "firmware_version", "firmware_origin_fork")
        lines += [" ".join(x.split()) for x in f.cli("device_info", 20).splitlines() if x.split(":")[0].strip() in wanted]
        lines.append("app: " + f.cli("loader info"))
        lines.append(f.cli("uptime"))
        try:
            f.screen_frame()
            lines.append("screen: OK (unlocked)")
        except (RuntimeError, TimeoutError) as e:
            lines.append(f"screen: FAILED - {e}")
    return "\n".join(lines)


@mcp.tool(annotations=EXTERNAL)
def flipper_listen(command: str, seconds: int = 10) -> str:
    """Run a CLI command that listens until interrupted, for `seconds`, then
    stop it (Ctrl+C) and return everything it captured. Use for receive/read
    commands that flipper_run_cli would time out on, e.g.
    'subghz rx 433920000 0', 'ir rx', 'ir rx raw', 'rfid read', 'ikey read',
    'log'. Hold the tag/remote to the Flipper while it runs."""
    with Flipper() as f:
        return f.cli_timed(command, max(1, seconds)) or "(nothing captured)"


@mcp.tool(annotations=ADDITIVE)
def flipper_led(r: int, g: int, b: int) -> str:
    """Set the RGB status LED (each channel 0-255)."""
    with Flipper() as f:
        for ch, v in (("r", r), ("g", g), ("b", b)):
            f.cli(f"led {ch} {max(0, min(255, v))}")
    return f"LED set to ({r},{g},{b})"


@mcp.tool(annotations=ADDITIVE)
def flipper_vibro(on: bool) -> str:
    """Turn the vibration motor on or off."""
    with Flipper() as f:
        return f.cli(f"vibro {1 if on else 0}") or ("vibro on" if on else "vibro off")


@mcp.tool(annotations=DESTRUCTIVE)
def flipper_reboot(mode: str = "normal") -> str:
    """Reboot the Flipper. mode: normal | dfu (bootloader)."""
    with Flipper() as f:
        f.s.write(b"power reboot2dfu\r" if mode == "dfu" else b"power reboot\r")
        time.sleep(0.5)
    return f"reboot ({mode}) sent"
