// base64_encode kernel (C++). A port of tasks/base64_encode/ref.c.
#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <string_view>

namespace {

constexpr std::array<std::uint8_t, 64> make_alphabet() noexcept {
    constexpr std::string_view chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::array<std::uint8_t, 64> table{};
    for (std::size_t i = 0; i < table.size(); ++i) table[i] = static_cast<std::uint8_t>(chars[i]);
    return table;
}

constexpr std::array<std::uint8_t, 64> alphabet = make_alphabet();

// Writes the Base64 text of `src` to the front of `dst` and returns its length,
// 4 * ceil(src.size() / 3). `dst` must have room for that many bytes.
std::size_t base64_encode(std::span<const std::uint8_t> src, std::span<std::uint8_t> dst) noexcept {
    const std::size_t len = src.size();
    std::size_t i = 0;
    std::size_t o = 0;
    for (; i + 3 <= len; i += 3) {
        const std::uint32_t v = std::uint32_t{src[i]} << 16 | std::uint32_t{src[i + 1]} << 8 | src[i + 2];
        dst[o++] = alphabet[v >> 18];
        dst[o++] = alphabet[(v >> 12) & 63];
        dst[o++] = alphabet[(v >> 6) & 63];
        dst[o++] = alphabet[v & 63];
    }
    if (len - i == 1) {
        const std::uint32_t v = std::uint32_t{src[i]} << 16;
        dst[o++] = alphabet[v >> 18];
        dst[o++] = alphabet[(v >> 12) & 63];
        dst[o++] = '=';
        dst[o++] = '=';
    } else if (len - i == 2) {
        const std::uint32_t v = std::uint32_t{src[i]} << 16 | std::uint32_t{src[i + 1]} << 8;
        dst[o++] = alphabet[v >> 18];
        dst[o++] = alphabet[(v >> 12) & 63];
        dst[o++] = alphabet[(v >> 6) & 63];
        dst[o++] = '=';
    }
    return o;
}

// The output buffer: allocated (uninitialized) on the first call to run, then reused.
std::unique_ptr<std::uint8_t[]> out;
std::size_t out_capacity = 0;
std::size_t out_len = 0;

}  // namespace

std::uint64_t run(std::span<const std::uint8_t> data) {
    const std::size_t needed = 4 * ((data.size() + 2) / 3);
    if (!out || out_capacity < needed) {
        out = std::make_unique_for_overwrite<std::uint8_t[]>(needed);
        out_capacity = needed;
    }
    out_len = base64_encode(data, std::span{out.get(), out_capacity});
    return out_len;
}

std::uint64_t digest() {
    std::uint64_t hash = 0xcbf29ce484222325ull;  // FNV-1a
    for (const std::uint8_t byte : std::span{out.get(), out_len}) {
        hash = (hash ^ byte) * 0x100000001b3ull;
    }
    return hash;
}
