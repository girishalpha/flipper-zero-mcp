"""BadUSB (DuckyScript) tools.

Authoring and running keystroke-injection scripts. The scripts run against
whatever host the Flipper's USB is plugged into - use only on a PC you own or
are authorised to test.
"""

import hashlib

from ..app import EXTERNAL_DESTRUCTIVE, OVERWRITE, mcp
from ..transport import Flipper

BADUSB_DIR = "/ext/badusb"


def _normalise_name(filename: str) -> str:
    """Ensure a .txt extension (DuckyScript files are plain text)."""
    return filename if filename.lower().endswith(".txt") else filename + ".txt"


@mcp.tool(annotations=OVERWRITE)
def flipper_badusb_create(filename: str, ducky_script: str) -> str:
    """Write a BadUSB DuckyScript to /ext/badusb/<filename> on the Flipper, for
    testing a PC you own. The agent authors the DuckyScript (DELAY, STRING, ENTER,
    GUI r, CTRL ALT DEL, etc.). Adds a .txt extension if missing. Does not run it."""
    filename = _normalise_name(filename)
    path = f"{BADUSB_DIR}/{filename}"
    data = ducky_script.replace("\r\n", "\n").encode()
    with Flipper() as f:
        f.cli(f'storage mkdir {BADUSB_DIR}')
        f.write_file(path, data)
        md5 = f.cli(f'storage md5 "{path}"', 60).split()[-1].lower()
    ok = md5 == hashlib.md5(data, usedforsecurity=False).hexdigest()  # nosec B324
    return f"{'OK' if ok else 'MISMATCH'}: wrote {len(data)} bytes -> {path}"


@mcp.tool(annotations=EXTERNAL_DESTRUCTIVE)
def flipper_badusb_run(filename: str) -> str:
    """Launch the Bad USB app with a saved DuckyScript from /ext/badusb/. The
    script runs against whatever host the Flipper's USB is plugged into — use
    only on a PC you own or are authorised to test."""
    filename = _normalise_name(filename)
    path = f"{BADUSB_DIR}/{filename}"
    with Flipper() as f:
        return f.cli(f'loader open "Bad USB" "{path}"', 20) or f"launched Bad USB with {path}"
