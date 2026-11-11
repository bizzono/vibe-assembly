"""utf8_validate kernel (Python): port of tasks/utf8_validate/ref.c, a direct
transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard."""


def run(s):
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if c < 0x80:
            i += 1
        elif 0xC2 <= c <= 0xDF:
            if n - i < 2 or not 0x80 <= s[i + 1] <= 0xBF:
                return 0
            i += 2
        elif 0xE0 <= c <= 0xEF:
            lo = 0xA0 if c == 0xE0 else 0x80  # E0: no overlong encodings
            hi = 0x9F if c == 0xED else 0xBF  # ED: no UTF-16 surrogates
            if n - i < 3 or not lo <= s[i + 1] <= hi or not 0x80 <= s[i + 2] <= 0xBF:
                return 0
            i += 3
        elif 0xF0 <= c <= 0xF4:
            lo = 0x90 if c == 0xF0 else 0x80  # F0: no overlong encodings
            hi = 0x8F if c == 0xF4 else 0xBF  # F4: nothing above U+10FFFF
            if (n - i < 4 or not lo <= s[i + 1] <= hi or not 0x80 <= s[i + 2] <= 0xBF
                    or not 0x80 <= s[i + 3] <= 0xBF):
                return 0
            i += 4
        else:
            return 0  # 80..C1 and F5..FF never start a sequence
    return 1


def digest():
    return 0
