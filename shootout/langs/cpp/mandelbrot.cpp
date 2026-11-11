// mandelbrot kernel (C++). A port of tasks/mandelbrot/ref.c.
// The result must be bit-exact: every *, + and - below is its own correctly-rounded
// IEEE-754 operation, so no fused multiply-add. The runner builds this file with
// -ffp-contract=off; the pragma says the same thing in the source.
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>

#pragma STDC FP_CONTRACT OFF

namespace {

std::uint64_t mandelbrot(std::uint64_t width, std::uint64_t height, std::uint64_t max_iter) noexcept {
    if (width == 0 || height == 0) return 0;
    const double dx = 3.0 / static_cast<double>(width);
    const double dy = 3.0 / static_cast<double>(height);
    std::uint64_t total = 0;
    for (std::uint64_t py = 0; py < height; ++py) {
        const double ci = -1.5 + static_cast<double>(py) * dy;
        for (std::uint64_t px = 0; px < width; ++px) {
            const double cr = -2.0 + static_cast<double>(px) * dx;
            double zr = 0.0;
            double zi = 0.0;
            std::uint64_t n = 0;
            while (n < max_iter) {
                const double zr2 = zr * zr;
                const double zi2 = zi * zi;
                if (zr2 + zi2 > 4.0) break;
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
                ++n;
            }
            total += n;
        }
    }
    return total;
}

constexpr std::uint32_t read_le32(std::span<const std::uint8_t, 4> bytes) noexcept {
    return std::uint32_t{bytes[0]} | std::uint32_t{bytes[1]} << 8 | std::uint32_t{bytes[2]} << 16 |
           std::uint32_t{bytes[3]} << 24;
}

}  // namespace

// The input is width, height, max_iter as little-endian u32 (all zero if it is too short).
std::uint64_t run(std::span<const std::uint8_t> data) {
    std::array<std::uint32_t, 3> params{};
    if (data.size() >= 4 * params.size()) {
        for (std::size_t i = 0; i < params.size(); ++i) params[i] = read_le32(data.subspan(4 * i).first<4>());
    }
    return mandelbrot(params[0], params[1], params[2]);
}

std::uint64_t digest() { return 0; }
