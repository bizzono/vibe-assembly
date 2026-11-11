"""utf8_validate kernel (Python): port of tasks/utf8_validate/ref.c, a direct
transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.

The reference walks the buffer with an index; here the cursor is a bytes iterator, the
usual way to consume a variable number of items per step in Python. The outer `for`
takes each lead byte and next() takes its continuation bytes. Past the end next()
gives -1, which is in no range, so a sequence cut short by the end of the buffer is
rejected just as the reference's `n - i < k` test rejects it."""


def run(s):
    it = iter(s)  # yields ints
    for c in it:
        if c < 0x80:
            continue
        elif 0xC2 <= c <= 0xDF:
            if not 0x80 <= next(it, -1) <= 0xBF:
                return 0
        elif 0xE0 <= c <= 0xEF:
            lo = 0xA0 if c == 0xE0 else 0x80  # E0: no overlong encodings
            hi = 0x9F if c == 0xED else 0xBF  # ED: no UTF-16 surrogates
            if not lo <= next(it, -1) <= hi or not 0x80 <= next(it, -1) <= 0xBF:
                return 0
        elif 0xF0 <= c <= 0xF4:
            lo = 0x90 if c == 0xF0 else 0x80  # F0: no overlong encodings
            hi = 0x8F if c == 0xF4 else 0xBF  # F4: nothing above U+10FFFF
            if (not lo <= next(it, -1) <= hi or not 0x80 <= next(it, -1) <= 0xBF
                    or not 0x80 <= next(it, -1) <= 0xBF):
                return 0
        else:
            return 0  # 80..C1 and F5..FF never start a sequence
    return 1


def digest():
    return 0
