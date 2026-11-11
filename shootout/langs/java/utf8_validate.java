/* utf8_validate kernel (Java): a port of tasks/utf8_validate/ref.c, itself a direct
 * transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard. */
final class Kernel {
    private Kernel() {}

    private static boolean in(int c, int lo, int hi) {
        return c >= lo && c <= hi;
    }

    static long run(byte[] s) {
        final int n = s.length;
        int i = 0;
        while (i < n) {
            int c = s[i] & 0xFF;
            if (c < 0x80) {
                i += 1;
            } else if (in(c, 0xC2, 0xDF)) {
                if (n - i < 2 || !in(s[i + 1] & 0xFF, 0x80, 0xBF)) return 0;
                i += 2;
            } else if (in(c, 0xE0, 0xEF)) {
                int lo = c == 0xE0 ? 0xA0 : 0x80; /* E0: no overlong encodings */
                int hi = c == 0xED ? 0x9F : 0xBF; /* ED: no UTF-16 surrogates */
                if (n - i < 3 || !in(s[i + 1] & 0xFF, lo, hi) || !in(s[i + 2] & 0xFF, 0x80, 0xBF)) return 0;
                i += 3;
            } else if (in(c, 0xF0, 0xF4)) {
                int lo = c == 0xF0 ? 0x90 : 0x80; /* F0: no overlong encodings */
                int hi = c == 0xF4 ? 0x8F : 0xBF; /* F4: nothing above U+10FFFF */
                if (n - i < 4 || !in(s[i + 1] & 0xFF, lo, hi) || !in(s[i + 2] & 0xFF, 0x80, 0xBF)
                        || !in(s[i + 3] & 0xFF, 0x80, 0xBF)) {
                    return 0;
                }
                i += 4;
            } else {
                return 0; /* 80..C1 and F5..FF never start a sequence */
            }
        }
        return 1;
    }

    static long digest() {
        return 0;
    }
}
