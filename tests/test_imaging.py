import struct
import unittest
import zlib

from flipper_mcp.imaging import SCREEN_H, SCREEN_W, frame_png


def chunks(png: bytes):
    """Yield (type, body) for each PNG chunk, checking every CRC."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    i = 8
    while i < len(png):
        n = struct.unpack(">I", png[i:i + 4])[0]
        kind, body = png[i + 4:i + 8], png[i + 8:i + 8 + n]
        crc = struct.unpack(">I", png[i + 8 + n:i + 12 + n])[0]
        assert crc == zlib.crc32(kind + body), f"bad CRC in {kind!r}"
        yield kind, body
        i += 12 + n


def pixels(png: bytes, scale: int):
    """Decode the palette-index image into rows of ints."""
    idat = b"".join(b for k, b in chunks(png) if k == b"IDAT")
    raw = zlib.decompress(idat)
    stride = 1 + SCREEN_W * scale
    return [list(raw[r * stride + 1:(r + 1) * stride]) for r in range(SCREEN_H * scale)]


BLANK = bytes(SCREEN_W * SCREEN_H // 8)


class FramePng(unittest.TestCase):
    def test_valid_png_with_expected_size(self):
        png = frame_png(BLANK)
        ihdr = dict(chunks(png))[b"IHDR"]
        width, height = struct.unpack(">II", ihdr[:8])
        self.assertEqual((width, height), (SCREEN_W * 4, SCREEN_H * 4))

    def test_scale_changes_size(self):
        ihdr = dict(chunks(frame_png(BLANK, scale=1)))[b"IHDR"]
        self.assertEqual(struct.unpack(">II", ihdr[:8]), (SCREEN_W, SCREEN_H))

    def test_blank_frame_is_all_background(self):
        self.assertEqual({p for row in pixels(frame_png(BLANK, scale=1), 1) for p in row}, {0})

    def test_lsb_of_first_byte_is_top_left_pixel(self):
        data = bytearray(BLANK)
        data[0] = 0x01
        rows = pixels(frame_png(bytes(data), scale=1), 1)
        self.assertEqual(rows[0][0], 1)
        self.assertEqual(sum(map(sum, rows)), 1)  # nothing else lit

    def test_second_page_starts_at_row_eight(self):
        data = bytearray(BLANK)
        data[SCREEN_W] = 0x01  # page 1, column 0
        self.assertEqual(pixels(frame_png(bytes(data), scale=1), 1)[8][0], 1)

    def test_flipped_rotates_180(self):
        data = bytearray(BLANK)
        data[0] = 0x01
        rows = pixels(frame_png(bytes(data), flipped=True, scale=1), 1)
        self.assertEqual(rows[SCREEN_H - 1][SCREEN_W - 1], 1)
        self.assertEqual(sum(map(sum, rows)), 1)


if __name__ == "__main__":
    unittest.main()
