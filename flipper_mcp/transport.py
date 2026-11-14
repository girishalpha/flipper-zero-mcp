"""Serial transport to a Flipper Zero.

Every tool opens one short-lived `Flipper` session (open -> do -> close) so the
server never holds the serial port hostage, and so each call recovers cleanly
from the RPC-takeover / DTR-reset quirks that break naive serial tools.

Port is auto-detected by USB VID:PID 0483:5740, overridable with env FLIPPER_PORT.
"""

import os
import re
import time

import serial
import serial.tools.list_ports

from .protocol import decode_fields, read_varint

BAUD = 230400
PROMPT = b">: "


def find_port() -> str:
    """Return the Flipper's serial port: FLIPPER_PORT if set, else auto-detect."""
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
                    n, i = read_varint(buf, 0)
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
                main = decode_fields(message())
                if main.get(2):
                    raise RuntimeError(f"Flipper RPC error (command_status {main[2]})")
                if 22 in main:  # gui_screen_frame
                    frame = decode_fields(main[22])
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
