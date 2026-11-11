"""crc32 kernel (Python): port of tasks/crc32/ref.c, the textbook table-driven CRC-32
with one table lookup per input byte."""


def _make_table():
    """The 256-entry table for the reflected polynomial 0xEDB88320 (the same values as
    the literal table in ref.c)."""
    table = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = 0xEDB88320 ^ (c >> 1) if c & 1 else c >> 1
        table.append(c)
    return tuple(table)


_CRC_TABLE = _make_table()  # built once, at import


def run(data):
    table = _CRC_TABLE
    crc = 0xFFFFFFFF
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def digest():
    return 0
