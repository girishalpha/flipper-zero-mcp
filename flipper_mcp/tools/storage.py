"""SD-card storage tools: list, info, read, download, upload, mkdir, delete."""

import base64
import hashlib

from ..app import mcp
from ..transport import Flipper


@mcp.tool()
def flipper_storage_list(path: str = "/ext") -> str:
    """List a directory on the Flipper SD (e.g. /ext, /ext/subghz, /ext/nfc)."""
    with Flipper() as f:
        return f.cli(f'storage list "{path}"', 30)


@mcp.tool()
def flipper_storage_info() -> str:
    """Show SD card label, filesystem and free space."""
    with Flipper() as f:
        return f.cli("storage info /ext", 15)


@mcp.tool()
def flipper_storage_read(path: str, max_bytes: int = 65536) -> str:
    """Read a file from the Flipper. Returns UTF-8 text if printable, else
    base64 (prefixed 'base64:'). Caps at max_bytes."""
    with Flipper() as f:
        data = f.read_file(path, max_bytes)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return "base64:" + base64.b64encode(data).decode()


@mcp.tool()
def flipper_storage_download(remote_path: str, local_path: str) -> str:
    """Download a file from the Flipper to the PC (binary-safe, up to 64 MB)."""
    with Flipper() as f:
        data = f.read_file(remote_path, 1 << 26)
    with open(local_path, "wb") as fh:
        fh.write(data)
    return f"OK: {len(data)} bytes -> {local_path}"


@mcp.tool()
def flipper_storage_write(remote_path: str, local_path: str) -> str:
    """Upload a local PC file to the Flipper SD and verify it by MD5."""
    with open(local_path, "rb") as fh:
        data = fh.read()
    with Flipper() as f:
        f.write_file(remote_path, data)
        remote_md5 = f.cli(f'storage md5 "{remote_path}"', 60).split()[-1].lower()
    ok = remote_md5 == hashlib.md5(data).hexdigest()
    return f"{'OK' if ok else 'MISMATCH'}: {len(data)} bytes -> {remote_path}"


@mcp.tool()
def flipper_storage_mkdir(path: str) -> str:
    """Create a directory on the Flipper SD."""
    with Flipper() as f:
        return f.cli(f'storage mkdir "{path}"') or "OK"


@mcp.tool()
def flipper_storage_delete(path: str) -> str:
    """Delete a file or (empty) directory on the Flipper SD."""
    with Flipper() as f:
        return f.cli(f'storage remove "{path}"') or "OK"
