// utf8_validate kernel (Swift): port of tasks/utf8_validate/ref.c, a direct
// transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.

@inline(__always)
private func inRange(_ c: UInt8, _ lo: UInt8, _ hi: UInt8) -> Bool {
    return c >= lo && c <= hi
}

func utf8Validate(_ s: UnsafeBufferPointer<UInt8>) -> UInt64 {
    let n = s.count
    var i = 0
    while i < n {
        let c = s[i]
        if c < 0x80 {
            i &+= 1
        } else if inRange(c, 0xC2, 0xDF) {
            if n &- i < 2 || !inRange(s[i &+ 1], 0x80, 0xBF) { return 0 }
            i &+= 2
        } else if inRange(c, 0xE0, 0xEF) {
            let lo: UInt8 = c == 0xE0 ? 0xA0 : 0x80  // E0: no overlong encodings
            let hi: UInt8 = c == 0xED ? 0x9F : 0xBF  // ED: no UTF-16 surrogates
            if n &- i < 3 || !inRange(s[i &+ 1], lo, hi) || !inRange(s[i &+ 2], 0x80, 0xBF) {
                return 0
            }
            i &+= 3
        } else if inRange(c, 0xF0, 0xF4) {
            let lo: UInt8 = c == 0xF0 ? 0x90 : 0x80  // F0: no overlong encodings
            let hi: UInt8 = c == 0xF4 ? 0x8F : 0xBF  // F4: nothing above U+10FFFF
            if n &- i < 4 || !inRange(s[i &+ 1], lo, hi) || !inRange(s[i &+ 2], 0x80, 0xBF)
                || !inRange(s[i &+ 3], 0x80, 0xBF)
            {
                return 0
            }
            i &+= 4
        } else {
            return 0  // 80..C1 and F5..FF never start a sequence
        }
    }
    return 1
}

func run(_ data: UnsafeBufferPointer<UInt8>) -> UInt64 { return utf8Validate(data) }
func digest() -> UInt64 { return 0 }
