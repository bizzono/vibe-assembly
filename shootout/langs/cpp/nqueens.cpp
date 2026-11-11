// nqueens kernel (C++). A port of tasks/nqueens/ref.c: the textbook bitmask
// backtracking search, one queen per row, every complete placement counted.
#include <cstdint>
#include <span>

namespace {

std::uint64_t place(std::uint32_t all, std::uint32_t cols, std::uint32_t diag_l, std::uint32_t diag_r) noexcept {
    if (cols == all) return 1;
    std::uint64_t count = 0;
    std::uint32_t open = all & ~(cols | diag_l | diag_r);
    while (open != 0) {
        const std::uint32_t bit = open & -open;  // lowest free square in this row
        open ^= bit;
        count += place(all, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1);
    }
    return count;
}

std::uint64_t nqueens(std::uint64_t n) noexcept {
    if (n > 31) return 0;
    const auto all = static_cast<std::uint32_t>((std::uint64_t{1} << n) - 1);
    return place(all, 0, 0, 0);
}

constexpr std::uint32_t read_le32(std::span<const std::uint8_t, 4> bytes) noexcept {
    return std::uint32_t{bytes[0]} | std::uint32_t{bytes[1]} << 8 | std::uint32_t{bytes[2]} << 16 |
           std::uint32_t{bytes[3]} << 24;
}

}  // namespace

// The input is n as a little-endian u32 (0 if it is too short).
std::uint64_t run(std::span<const std::uint8_t> data) {
    const std::uint32_t n = data.size() >= 4 ? read_le32(data.first<4>()) : 0;
    return nqueens(n);
}

std::uint64_t digest() { return 0; }
