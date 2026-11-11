// utf8_validate kernel (C++). A port of tasks/utf8_validate/ref.c: a direct
// transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.
#include <cstddef>
#include <cstdint>
#include <span>

namespace {

constexpr bool in(std::uint8_t c, std::uint8_t lo, std::uint8_t hi) noexcept {
    return c >= lo && c <= hi;
}

std::uint64_t utf8_validate(std::span<const std::uint8_t> s) noexcept {
    const std::size_t n = s.size();
    std::size_t i = 0;
    while (i < n) {
        const std::uint8_t c = s[i];
        if (c < 0x80) {
            i += 1;
        } else if (in(c, 0xC2, 0xDF)) {
            if (n - i < 2 || !in(s[i + 1], 0x80, 0xBF)) return 0;
            i += 2;
        } else if (in(c, 0xE0, 0xEF)) {
            const std::uint8_t lo = c == 0xE0 ? 0xA0 : 0x80;  // E0: no overlong encodings
            const std::uint8_t hi = c == 0xED ? 0x9F : 0xBF;  // ED: no UTF-16 surrogates
            if (n - i < 3 || !in(s[i + 1], lo, hi) || !in(s[i + 2], 0x80, 0xBF)) return 0;
            i += 3;
        } else if (in(c, 0xF0, 0xF4)) {
            const std::uint8_t lo = c == 0xF0 ? 0x90 : 0x80;  // F0: no overlong encodings
            const std::uint8_t hi = c == 0xF4 ? 0x8F : 0xBF;  // F4: nothing above U+10FFFF
            if (n - i < 4 || !in(s[i + 1], lo, hi) || !in(s[i + 2], 0x80, 0xBF) ||
                !in(s[i + 3], 0x80, 0xBF)) {
                return 0;
            }
            i += 4;
        } else {
            return 0;  // 80..C1 and F5..FF never start a sequence
        }
    }
    return 1;
}

}  // namespace

std::uint64_t run(std::span<const std::uint8_t> data) { return utf8_validate(data); }
std::uint64_t digest() { return 0; }
