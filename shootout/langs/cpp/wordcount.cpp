// wordcount kernel (C++). A port of tasks/wordcount/ref.c.
#include <cstdint>
#include <span>

namespace {

// Exactly the six ASCII whitespace bytes: space, \t \n \v \f \r.
constexpr bool is_space(std::uint8_t c) noexcept {
    return c == ' ' || (c >= '\t' && c <= '\r');
}

std::uint64_t wordcount(std::span<const std::uint8_t> buf) noexcept {
    std::uint64_t words = 0;
    bool in_word = false;
    for (const std::uint8_t c : buf) {
        if (is_space(c)) {
            in_word = false;
        } else if (!in_word) {
            in_word = true;
            ++words;
        }
    }
    return words;
}

}  // namespace

std::uint64_t run(std::span<const std::uint8_t> data) { return wordcount(data); }
std::uint64_t digest() { return 0; }
