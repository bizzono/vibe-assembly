// crc32 kernel (C++). A port of tasks/crc32/ref.c: the textbook table-driven CRC-32,
// one table lookup per input byte. The table is built at compile time.
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

namespace {

constexpr std::array<std::uint32_t, 256> make_crc_table() noexcept {
    std::array<std::uint32_t, 256> table{};
    for (std::uint32_t i = 0; i < 256; ++i) {
        std::uint32_t c = i;
        for (int bit = 0; bit < 8; ++bit) {
            c = (c & 1u) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;  // reflected polynomial
        }
        table[i] = c;
    }
    return table;
}

constexpr std::array<std::uint32_t, 256> crc_table = make_crc_table();
static_assert(crc_table[1] == 0x77073096u && crc_table[255] == 0x2d02ef8du);

std::uint64_t crc32_ieee(std::span<const std::uint8_t> buf) noexcept {
    std::uint32_t crc = 0xFFFFFFFFu;
    for (const std::uint8_t byte : buf) {
        crc = crc_table[(crc ^ byte) & 0xFFu] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

}  // namespace

std::uint64_t run(std::span<const std::uint8_t> data) { return crc32_ieee(data); }
std::uint64_t digest() { return 0; }
