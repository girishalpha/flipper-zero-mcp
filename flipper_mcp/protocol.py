"""Minimal protobuf decoding for the Flipper RPC protocol.

The Flipper's `start_rpc_session` speaks protobuf (`PB.Main` messages). We only
ever need to read varints and length-delimited fields, so rather than pull in
the full generated protobuf stubs we decode those two wire types by hand.
"""


def read_varint(buf: bytes, i: int):
    """Decode a base-128 varint at offset `i`. Returns (value, next_offset)."""
    n = shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7F) << shift
        if not b & 0x80:
            return n, i
        shift += 7


def decode_fields(buf: bytes) -> dict:
    """Decode a protobuf message into {field_number: value}.

    Only varint (wire type 0) and length-delimited (wire type 2) fields are
    supported - the only two the GUI/RPC messages we touch ever use.
    """
    out, i = {}, 0
    while i < len(buf):
        tag, i = read_varint(buf, i)
        if tag & 7 == 0:
            out[tag >> 3], i = read_varint(buf, i)
        elif tag & 7 == 2:
            n, i = read_varint(buf, i)
            out[tag >> 3] = buf[i:i + n]
            i += n
        else:
            raise ValueError(f"unexpected protobuf wire type {tag & 7}")
    return out
