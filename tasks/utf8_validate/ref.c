/* utf8_validate -- reference implementation (the oracle). See SPEC.md.
 * A direct transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the
 * Unicode Standard. */
#include <stddef.h>
#include <stdint.h>

static int in(uint8_t c, uint8_t lo, uint8_t hi) { return c >= lo && c <= hi; }

uint64_t utf8_validate(const uint8_t *s, size_t n) {
    size_t i = 0;
    while (i < n) {
        uint8_t c = s[i];
        if (c < 0x80) {
            i += 1;
        } else if (in(c, 0xC2, 0xDF)) {
            if (n - i < 2 || !in(s[i + 1], 0x80, 0xBF)) return 0;
            i += 2;
        } else if (in(c, 0xE0, 0xEF)) {
            uint8_t lo = c == 0xE0 ? 0xA0 : 0x80; /* E0: no overlong encodings */
            uint8_t hi = c == 0xED ? 0x9F : 0xBF; /* ED: no UTF-16 surrogates */
            if (n - i < 3 || !in(s[i + 1], lo, hi) || !in(s[i + 2], 0x80, 0xBF)) return 0;
            i += 3;
        } else if (in(c, 0xF0, 0xF4)) {
            uint8_t lo = c == 0xF0 ? 0x90 : 0x80; /* F0: no overlong encodings */
            uint8_t hi = c == 0xF4 ? 0x8F : 0xBF; /* F4: nothing above U+10FFFF */
            if (n - i < 4 || !in(s[i + 1], lo, hi) || !in(s[i + 2], 0x80, 0xBF) ||
                !in(s[i + 3], 0x80, 0xBF))
                return 0;
            i += 4;
        } else {
            return 0; /* 80..C1 and F5..FF never start a sequence */
        }
    }
    return 1;
}
