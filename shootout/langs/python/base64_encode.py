"""base64_encode kernel (Python): port of tasks/base64_encode/ref.c."""

_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_PAD = 0x3D  # '='

_out = None  # allocated on the first call, then reused
_out_len = 0


def _encode(src, dst):
    alphabet = _ALPHABET
    n = len(src)
    whole = n - n % 3
    o = 0
    for i in range(0, whole, 3):
        v = src[i] << 16 | src[i + 1] << 8 | src[i + 2]
        dst[o] = alphabet[v >> 18]
        dst[o + 1] = alphabet[(v >> 12) & 63]
        dst[o + 2] = alphabet[(v >> 6) & 63]
        dst[o + 3] = alphabet[v & 63]
        o += 4
    i = whole
    if n - i == 1:
        v = src[i] << 16
        dst[o] = alphabet[v >> 18]
        dst[o + 1] = alphabet[(v >> 12) & 63]
        dst[o + 2] = _PAD
        dst[o + 3] = _PAD
        o += 4
    elif n - i == 2:
        v = src[i] << 16 | src[i + 1] << 8
        dst[o] = alphabet[v >> 18]
        dst[o + 1] = alphabet[(v >> 12) & 63]
        dst[o + 2] = alphabet[(v >> 6) & 63]
        dst[o + 3] = _PAD
        o += 4
    return o


def run(data):
    global _out, _out_len
    if _out is None:
        _out = bytearray(4 * ((len(data) + 2) // 3))
    _out_len = _encode(data, _out)
    return _out_len


def digest():
    """64-bit FNV-1a of the bytes written by the last run. Not timed."""
    out = _out
    h = 0xCBF29CE484222325
    for i in range(_out_len):
        h = ((h ^ out[i]) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h
