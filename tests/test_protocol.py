import unittest

from flipper_mcp.protocol import decode_fields, read_varint


class ReadVarint(unittest.TestCase):
    def test_single_byte(self):
        self.assertEqual(read_varint(b"\x05", 0), (5, 1))

    def test_multi_byte(self):
        self.assertEqual(read_varint(b"\xac\x02", 0), (300, 2))

    def test_respects_offset(self):
        self.assertEqual(read_varint(b"\xff\x01", 1), (1, 2))

    def test_truncated_raises_index_error(self):
        # screen_frame() relies on this to know it needs more bytes
        with self.assertRaises(IndexError):
            read_varint(b"\x80", 0)


class DecodeFields(unittest.TestCase):
    def test_varint_field(self):
        self.assertEqual(decode_fields(b"\x08\x96\x01"), {1: 150})

    def test_length_delimited_field(self):
        self.assertEqual(decode_fields(b"\x12\x03abc"), {2: b"abc"})

    def test_mixed_fields(self):
        self.assertEqual(decode_fields(b"\x08\x01\x12\x02hi"), {1: 1, 2: b"hi"})

    def test_empty(self):
        self.assertEqual(decode_fields(b""), {})

    def test_unsupported_wire_type_raises(self):
        with self.assertRaises(ValueError):
            decode_fields(b"\x0d\x00\x00\x00\x00")  # field 1, wire type 5 (fixed32)


if __name__ == "__main__":
    unittest.main()
