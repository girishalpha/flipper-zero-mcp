"""Test doubles: a fake Flipper serial port, so no hardware is needed."""

PROMPT = b">: "


def varint(n: int) -> bytes:
    """Encode an int as a protobuf varint."""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def screen_frame_message(framebuffer: bytes, orientation: int = 0) -> bytes:
    """A length-prefixed PB.Main{gui_screen_frame{data, orientation}} message."""
    frame = b"\x0a" + varint(len(framebuffer)) + framebuffer + b"\x10" + varint(orientation)
    main = b"\xb2\x01" + varint(len(frame)) + frame  # field 22, length-delimited
    return varint(len(main)) + main


class FakeSerial:
    """Mimics the bits of serial.Serial that Flipper uses.

    `responses` maps a CLI line (no trailing CR) to the raw bytes the device
    prints after echoing the command and before the next prompt.
    """

    def __init__(self, responses=None, rpc_frame=None, silent=()):
        self.responses = dict(responses or {})
        self.rpc_frame = rpc_frame
        self.silent = set(silent)  # commands that echo but never return a prompt (until Ctrl+C)
        self.rx = bytearray()
        self.writes = []
        self.chunks = []  # payloads received after a `storage write_chunk`
        self._chunk_pending = False
        self.dtr = self.rts = False
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self, n=1):
        out, self.rx = bytes(self.rx[:n]), self.rx[n:]
        return out

    def reset_input_buffer(self):
        self.rx.clear()

    def flush(self):
        pass

    def close(self):
        self.closed = True

    def write(self, data: bytes):
        self.writes.append(data)
        if self._chunk_pending:  # raw payload following `storage write_chunk`
            self.chunks.append(data)
            self._chunk_pending = False
            self.rx += b"\r\n" + PROMPT
        elif data == b"\x03\r":  # break out of anything, land on a prompt
            self.rx += b"\r\n" + PROMPT
        elif data == b"\x03":  # Ctrl+C stops a silent (listening) command
            self.rx += b"^C\r\n" + PROMPT
        elif data == b"start_rpc_session\r" and self.rpc_frame is not None:
            self.rx += b"start_rpc_session\r\n" + self.rpc_frame
        elif data.endswith(b"\r"):
            line = data[:-1].decode()
            if line.startswith("storage write_chunk"):
                self._chunk_pending = True
                self.rx += line.encode() + b"\r\nReady\r\n"  # prompt comes after the payload
            elif line in self.silent:
                self.rx += line.encode() + b"\r\n"
            else:
                self.rx += line.encode() + b"\r\n" + self.responses.get(line, b"") + PROMPT
