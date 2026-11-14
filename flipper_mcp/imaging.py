"""Turn a raw Flipper framebuffer into a PNG.

The Flipper screen is 128x64, 1 bit per pixel. Over RPC we receive it in the
display's native layout (8 pages of 128 bytes, each byte a vertical column of 8
pixels, LSB on top). `frame_png` upscales and re-encodes it as a PNG coloured to
match the physical orange backlight.
"""

import struct
import zlib

SCREEN_W, SCREEN_H = 128, 64


def frame_png(data: bytes, flipped: bool = False, scale: int = 4) -> bytes:
    """Encode a raw 128x64 1-bpp framebuffer as a PNG.

    `flipped` handles the device's upside-down orientation; `scale` upscales
    each pixel so the 128x64 panel is legible when viewed on a PC.
    """
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
