// utf8_validate kernel (Go): port of tasks/utf8_validate/ref.c, a direct
// transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.
package main

func in(c, lo, hi byte) bool { return c >= lo && c <= hi }

func utf8Validate(s []byte) uint64 {
	n := len(s)
	i := 0
	for i < n {
		c := s[i]
		if c < 0x80 {
			i++
		} else if in(c, 0xC2, 0xDF) {
			if n-i < 2 || !in(s[i+1], 0x80, 0xBF) {
				return 0
			}
			i += 2
		} else if in(c, 0xE0, 0xEF) {
			lo, hi := byte(0x80), byte(0xBF)
			if c == 0xE0 { // E0: no overlong encodings
				lo = 0xA0
			}
			if c == 0xED { // ED: no UTF-16 surrogates
				hi = 0x9F
			}
			if n-i < 3 || !in(s[i+1], lo, hi) || !in(s[i+2], 0x80, 0xBF) {
				return 0
			}
			i += 3
		} else if in(c, 0xF0, 0xF4) {
			lo, hi := byte(0x80), byte(0xBF)
			if c == 0xF0 { // F0: no overlong encodings
				lo = 0x90
			}
			if c == 0xF4 { // F4: nothing above U+10FFFF
				hi = 0x8F
			}
			if n-i < 4 || !in(s[i+1], lo, hi) || !in(s[i+2], 0x80, 0xBF) ||
				!in(s[i+3], 0x80, 0xBF) {
				return 0
			}
			i += 4
		} else {
			return 0 // 80..C1 and F5..FF never start a sequence
		}
	}
	return 1
}

func run(data []byte) uint64 { return utf8Validate(data) }
func digest() uint64         { return 0 }
