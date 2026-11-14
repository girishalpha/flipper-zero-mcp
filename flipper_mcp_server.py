"""
Flipper Zero MCP server (local, full control).

Wraps the Flipper's serial CLI so Claude Code agents can drive the device.
Opens the serial port per call (open -> do -> close) so it never holds the
port hostage, and handles the RPC-takeover / DTR-reset quirks that break
naive serial tools.

Port: auto-detected by USB VID:PID 0483:5740, overridable with env FLIPPER_PORT.
Run standalone for a quick self-test:  python flipper_mcp_server.py --selftest
"""

import base64
import hashlib
import os
import re
import struct
import sys
import time
import zlib

import serial
import serial.tools.list_ports
from mcp.server.fastmcp import FastMCP, Image

BAUD = 230400
PROMPT = b">: "
SCREEN_W, SCREEN_H = 128, 64


def _varint(buf: bytes, i: int):
    n = shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def _pb_fields(buf: bytes) -> dict:
    """Minimal protobuf decode (varint + length-delimited fields only)."""
    out, i = {}, 0
    while i < len(buf):
        tag, i = _varint(buf, i)
        if tag & 7 == 0:
            out[tag >> 3], i = _varint(buf, i)
        elif tag & 7 == 2:
            n, i = _varint(buf, i)
            out[tag >> 3] = buf[i:i + n]
            i += n
        else:
            raise ValueError(f"unexpected protobuf wire type {tag & 7}")
    return out


def _frame_png(data: bytes, flipped: bool = False, scale: int = 4) -> bytes:
    """Encode a raw 128x64 1-bpp framebuffer as a PNG. The buffer is in the
    display's native layout: 8 pages of 128 bytes, each byte a column of 8
    pixels with the LSB on top."""
    raw = b""
    for y in range(SCREEN_H):
        row = bytearray(b"\0")
        for x in range(SCREEN_W):
            sx, sy = (SCREEN_W - 1 - x, SCREEN_H - 1 - y) if flipped else (x, y)
            on = data[(sy // 8) * SCREEN_W + sx] >> (sy % 8) & 1
            row += bytes([on]) * scale
        raw += bytes(row) * scale

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    ihdr = struct.pack(">IIBBBBB", SCREEN_W * scale, SCREEN_H * scale, 8, 3, 0, 0, 0)
    palette = bytes((0xFF, 0x82, 0x00, 0x00, 0x00, 0x00))  # orange backlight, black pixels
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"PLTE", palette)
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def find_port() -> str:
    env = os.environ.get("FLIPPER_PORT")
    if env:
        return env
    for p in serial.tools.list_ports.comports():
        if p.vid == 0x0483 and p.pid == 0x5740:
            return p.device
    raise RuntimeError("Flipper not found on USB (VID:PID 0483:5740). Set FLIPPER_PORT.")


class Flipper:
    """One short-lived serial session. Use as a context manager."""

    def __init__(self):
        self.s = serial.Serial(find_port(), BAUD, timeout=0.2, write_timeout=10)
        self.s.dtr = True
        self.s.rts = True
        time.sleep(0.8)
        self.s.reset_input_buffer()
        # Break any RPC session and land on a clean CLI prompt.
        for _ in range(3):
            self.s.write(b"\x03\r")
            try:
                self._read_prompt(3)
                self._drain()
                return
            except TimeoutError:
                pass
        raise RuntimeError("Flipper CLI not responding (is an app holding the USB link?)")

    def _drain(self):
        """Swallow late output (e.g. a second prompt) so it can't be mistaken for the next reply."""
        while self.s.read(256):
            pass

    def _read_prompt(self, timeout=15) -> bytes:
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            chunk = self.s.read(self.s.in_waiting or 1)
            if chunk:
                buf += chunk
                if buf.endswith(PROMPT):
                    return buf
        raise TimeoutError("no prompt")

    @staticmethod
    def _clean(raw: bytes, line: str) -> str:
        """Strip the command echo, ANSI colour codes and trailing prompt from CLI output."""
        out = re.sub(r"\x1b\[[0-9;]*m", "", raw.decode(errors="replace"))
        lines = out.replace("\r", "").split("\n")
        if lines and lines[0].strip() == line.strip():
            lines = lines[1:]
        return "\n".join(x for x in lines if x.strip() != ">:").strip()

    def cli(self, line: str, timeout=15) -> str:
        self.s.write(line.encode() + b"\r")
        return self._clean(self._read_prompt(timeout), line)

    def cli_timed(self, line: str, seconds: float) -> str:
        """Run a command that never returns on its own (rx/read loops): let it
        run for `seconds`, stop it with Ctrl+C and return what it printed."""
        self.s.write(line.encode() + b"\r")
        buf = b""
        end = time.time() + seconds
        while time.time() < end:
            buf += self.s.read(self.s.in_waiting or 1)
            if buf.endswith(PROMPT):  # finished on its own (error or one-shot command)
                break
        else:
            self.s.write(b"\x03")
            try:
                buf += self._read_prompt(5)
            except TimeoutError:
                pass
            self._drain()
        return self._clean(buf, line)

    def read_file(self, path: str, limit=1 << 20) -> bytes:
        self.s.write(f'storage read "{path}"\r'.encode())
        raw = self._read_prompt(60)

        m = re.search(rb"Size: (\d+)\r\n", raw)
        if not m:
            raise IOError(raw[-200:].decode(errors="replace"))
        size = min(int(m.group(1)), limit)
        return raw[m.end():m.end() + size]

    def write_file(self, path: str, data: bytes, chunk=4096):
        self.cli(f'storage remove "{path}"')
        for i in range(0, len(data), chunk):
            part = data[i:i + chunk]
            self.s.write(f'storage write_chunk "{path}" {len(part)}\r'.encode())
            buf = b""
            end = time.time() + 10
            while b"Ready" not in buf:
                if time.time() > end:
                    raise TimeoutError(f"no Ready for {path}")
                buf += self.s.read(self.s.in_waiting or 1)
            self.s.write(part)
            self._read_prompt(30)

    def screen_frame(self, timeout=5):
        """Grab one screen frame over RPC. Returns (1024 framebuffer bytes, orientation)."""
        buf = b""
        end = time.time() + timeout

        def fill():
            nonlocal buf
            if time.time() > end:
                raise TimeoutError("no screen frame from Flipper RPC")
            buf += self.s.read(self.s.in_waiting or 1)

        def message() -> bytes:
            nonlocal buf
            while True:
                if b"Session start error" in buf:
                    raise RuntimeError(
                        "Flipper refused the RPC session: the device is locked (keypad or "
                        "PIN). Run flipper_unlock, or unlock it on the device.")
                try:
                    n, i = _varint(buf, 0)
                    if len(buf) >= i + n:
                        msg, buf = buf[i:i + n], buf[i + n:]
                        return msg
                except IndexError:
                    pass
                fill()

        self.s.write(b"start_rpc_session\r")
        # Skip the command echo (a stale prompt may precede it); protobuf starts after its newline.
        while b"\n" not in buf.partition(b"start_rpc_session")[2]:
            fill()
        buf = buf.partition(b"start_rpc_session")[2].split(b"\n", 1)[1]
        # PB.Main{command_id=1, gui_start_screen_stream_request{}}
        self.s.write(b"\x05\x08\x01\xa2\x01\x00")
        try:
            while True:
                main = _pb_fields(message())
                if main.get(2):
                    raise RuntimeError(f"Flipper RPC error (command_status {main[2]})")
                if 22 in main:  # gui_screen_frame
                    frame = _pb_fields(main[22])
                    return frame[1], frame.get(2, 0)
        finally:
            # PB.Main{command_id=2, stop_session{}} -> back to the CLI
            self.s.write(b"\x05\x08\x02\x9a\x01\x00")
            self.s.flush()

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


mcp = FastMCP("flipper")


@mcp.tool()
def flipper_info() -> str:
    """Return the Flipper's device_info (firmware, hardware, radio, battery region)."""
    with Flipper() as f:
        return f.cli("device_info", 20)


@mcp.tool()
def flipper_run_cli(command: str, timeout: int = 15) -> str:
    """Run a raw Flipper CLI command and return its output. Full control escape
    hatch: e.g. 'subghz tx_from_file /ext/subghz/foo.sub 433920000', 'nfc',
    'ir tx', 'gpio set pa7 1', 'ps', 'free'. Use flipper_run_cli('help') to list."""
    with Flipper() as f:
        return f.cli(command, timeout)


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


@mcp.tool()
def flipper_led(r: int, g: int, b: int) -> str:
    """Set the RGB status LED (each channel 0-255)."""
    with Flipper() as f:
        for ch, v in (("r", r), ("g", g), ("b", b)):
            f.cli(f"led {ch} {max(0, min(255, v))}")
    return f"LED set to ({r},{g},{b})"


@mcp.tool()
def flipper_vibro(on: bool) -> str:
    """Turn the vibration motor on or off."""
    with Flipper() as f:
        return f.cli(f"vibro {1 if on else 0}") or ("vibro on" if on else "vibro off")


def _with_screen(f: Flipper, text: str):
    """Return [text, screenshot] for tools that report the screen after acting."""
    time.sleep(0.3)  # let the GUI redraw
    try:
        data, orientation = f.screen_frame()
    except (RuntimeError, TimeoutError) as e:
        return f"{text} (screenshot failed: {e})"
    return [text, Image(data=_frame_png(data, flipped=orientation == 1), format="png")]


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
    valid = {"up", "down", "left", "right", "ok", "back"}
    bad = [k for k in seq if k.split(":")[0] not in valid or k.split(":")[1:] not in ([], ["long"], ["short"])]
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


@mcp.tool()
def flipper_listen(command: str, seconds: int = 10) -> str:
    """Run a CLI command that listens until interrupted, for `seconds`, then
    stop it (Ctrl+C) and return everything it captured. Use for receive/read
    commands that flipper_run_cli would time out on, e.g.
    'subghz rx 433920000 0', 'ir rx', 'ir rx raw', 'rfid read', 'ikey read',
    'log'. Hold the tag/remote to the Flipper while it runs."""
    with Flipper() as f:
        return f.cli_timed(command, max(1, seconds)) or "(nothing captured)"


@mcp.tool()
def flipper_screenshot(save_path: str = "") -> Image:
    """Capture the Flipper's current screen (128x64, upscaled 4x) as a PNG so you
    can see what a press/navigate did. Optionally also save it to save_path on the PC."""
    with Flipper() as f:
        data, orientation = f.screen_frame()
    png = _frame_png(data, flipped=orientation == 1)
    if save_path:
        with open(save_path, "wb") as fh:
            fh.write(png)
    return Image(data=png, format="png")


@mcp.tool()
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


@mcp.tool()
def flipper_apps_running() -> str:
    """Show the currently running app (loader info)."""
    with Flipper() as f:
        return f.cli("loader info", 15)


@mcp.tool()
def flipper_loader_open(app: str, args: str = "") -> str:
    """Launch an app by name, optionally with an argument (e.g. a file path).
    Example: flipper_loader_open('Sub-GHz'), or open an app with a saved file."""
    cmd = f'loader open "{app}"' + (f' "{args}"' if args else "")
    with Flipper() as f:
        return f.cli(cmd, 20) or f"opened {app}"


@mcp.tool()
def flipper_loader_close() -> str:
    """Close the currently running app."""
    with Flipper() as f:
        return f.cli("loader close", 15) or "closed"


@mcp.tool()
def flipper_reboot(mode: str = "normal") -> str:
    """Reboot the Flipper. mode: normal | dfu (bootloader)."""
    with Flipper() as f:
        f.s.write(b"power reboot2dfu\r" if mode == "dfu" else b"power reboot\r")
        time.sleep(0.5)
    return f"reboot ({mode}) sent"


@mcp.tool()
def flipper_badusb_create(filename: str, ducky_script: str) -> str:
    """Write a BadUSB DuckyScript to /ext/badusb/<filename> on the Flipper, for
    testing a PC you own. The agent authors the DuckyScript (DELAY, STRING, ENTER,
    GUI r, CTRL ALT DEL, etc.). Adds a .txt extension if missing. Does not run it."""
    if not filename.lower().endswith(".txt"):
        filename += ".txt"
    path = f"/ext/badusb/{filename}"
    data = ducky_script.replace("\r\n", "\n").encode()
    with Flipper() as f:
        f.cli('storage mkdir /ext/badusb')
        f.write_file(path, data)
        md5 = f.cli(f'storage md5 "{path}"', 60).split()[-1].lower()
    ok = md5 == hashlib.md5(data).hexdigest()
    return f"{'OK' if ok else 'MISMATCH'}: wrote {len(data)} bytes -> {path}"


@mcp.tool()
def flipper_badusb_run(filename: str) -> str:
    """Launch the Bad USB app with a saved DuckyScript from /ext/badusb/. The
    script runs against whatever host the Flipper's USB is plugged into — use
    only on a PC you own or are authorised to test."""
    if not filename.lower().endswith(".txt"):
        filename += ".txt"
    path = f"/ext/badusb/{filename}"
    with Flipper() as f:
        return f.cli(f'loader open "Bad USB" "{path}"', 20) or f"launched Bad USB with {path}"


@mcp.tool()
def flipper_subghz_tx(path: str, frequency: int = 433920000) -> str:
    """Transmit a saved Sub-GHz .sub file at the given frequency (Hz). Transmit
    only on bands legal where you are, to devices you own (e.g. replay your own
    garage/gate remote capture)."""
    with Flipper() as f:
        return f.cli(f'subghz tx_from_file "{path}" {frequency}', 30)


def _selftest():
    with Flipper() as f:
        info = f.cli("device_info", 20)
        print(info.splitlines()[0] if info else "no reply")
        print("storage:", f.cli("storage info /ext", 15).splitlines()[0])
    print("self-test OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        mcp.run()
