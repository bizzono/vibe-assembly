//! utf8_validate kernel (Zig): port of tasks/utf8_validate/ref.c.
//! A direct transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the
//! Unicode Standard.

fn in(c: u8, lo: u8, hi: u8) bool {
    return c >= lo and c <= hi;
}

fn utf8Validate(s: []const u8) bool {
    const n = s.len;
    var i: usize = 0;
    while (i < n) {
        const c = s[i];
        if (c < 0x80) {
            i += 1;
        } else if (in(c, 0xC2, 0xDF)) {
            if (n - i < 2 or !in(s[i + 1], 0x80, 0xBF)) return false;
            i += 2;
        } else if (in(c, 0xE0, 0xEF)) {
            const lo: u8 = if (c == 0xE0) 0xA0 else 0x80; // E0: no overlong encodings
            const hi: u8 = if (c == 0xED) 0x9F else 0xBF; // ED: no UTF-16 surrogates
            if (n - i < 3 or !in(s[i + 1], lo, hi) or !in(s[i + 2], 0x80, 0xBF)) return false;
            i += 3;
        } else if (in(c, 0xF0, 0xF4)) {
            const lo: u8 = if (c == 0xF0) 0x90 else 0x80; // F0: no overlong encodings
            const hi: u8 = if (c == 0xF4) 0x8F else 0xBF; // F4: nothing above U+10FFFF
            if (n - i < 4 or !in(s[i + 1], lo, hi) or !in(s[i + 2], 0x80, 0xBF) or
                !in(s[i + 3], 0x80, 0xBF))
                return false;
            i += 4;
        } else {
            return false; // 80..C1 and F5..FF never start a sequence
        }
    }
    return true;
}

pub fn run(data: []const u8) u64 {
    return @intFromBool(utf8Validate(data));
}

pub fn digest() u64 {
    return 0;
}
