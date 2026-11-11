//! utf8_validate kernel (Rust). A port of tasks/utf8_validate/ref.c: a direct
//! transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.
//!
//! The reference walks an index and checks `n - i` before reading the continuation
//! bytes; here the unread input is a slice and the slice patterns do that length check.

fn within(c: u8, lo: u8, hi: u8) -> bool {
    lo <= c && c <= hi
}

fn utf8_validate(s: &[u8]) -> u64 {
    let mut rest = s;
    while let [c, tail @ ..] = rest {
        let c = *c;
        if c < 0x80 {
            rest = tail;
        } else if within(c, 0xC2, 0xDF) {
            match tail {
                [b1, tail @ ..] if within(*b1, 0x80, 0xBF) => rest = tail,
                _ => return 0,
            }
        } else if within(c, 0xE0, 0xEF) {
            let lo = if c == 0xE0 { 0xA0 } else { 0x80 }; // E0: no overlong encodings
            let hi = if c == 0xED { 0x9F } else { 0xBF }; // ED: no UTF-16 surrogates
            match tail {
                [b1, b2, tail @ ..] if within(*b1, lo, hi) && within(*b2, 0x80, 0xBF) => rest = tail,
                _ => return 0,
            }
        } else if within(c, 0xF0, 0xF4) {
            let lo = if c == 0xF0 { 0x90 } else { 0x80 }; // F0: no overlong encodings
            let hi = if c == 0xF4 { 0x8F } else { 0xBF }; // F4: nothing above U+10FFFF
            match tail {
                [b1, b2, b3, tail @ ..]
                    if within(*b1, lo, hi) && within(*b2, 0x80, 0xBF) && within(*b3, 0x80, 0xBF) =>
                {
                    rest = tail
                }
                _ => return 0,
            }
        } else {
            return 0; // 80..C1 and F5..FF never start a sequence
        }
    }
    1
}

pub fn run(data: &[u8]) -> u64 {
    utf8_validate(data)
}

pub fn digest() -> u64 {
    0
}
