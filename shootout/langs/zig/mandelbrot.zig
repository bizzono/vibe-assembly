//! mandelbrot kernel (Zig): port of tasks/mandelbrot/ref.c.
//! Zig's default (strict) float mode never fuses a multiply and an add, so every
//! `*`, `+`, `-` below is its own correctly-rounded IEEE-754 binary64 operation.
const std = @import("std");

fn mandelbrot(width: u64, height: u64, max_iter: u64) u64 {
    var total: u64 = 0;
    if (width == 0 or height == 0) return 0;
    const dx = 3.0 / @as(f64, @floatFromInt(width));
    const dy = 3.0 / @as(f64, @floatFromInt(height));
    var py: u64 = 0;
    while (py < height) : (py += 1) {
        const ci = -1.5 + @as(f64, @floatFromInt(py)) * dy;
        var px: u64 = 0;
        while (px < width) : (px += 1) {
            const cr = -2.0 + @as(f64, @floatFromInt(px)) * dx;
            var zr: f64 = 0.0;
            var zi: f64 = 0.0;
            var n: u64 = 0;
            while (n < max_iter) : (n += 1) {
                const zr2 = zr * zr;
                const zi2 = zi * zi;
                if (zr2 + zi2 > 4.0) break;
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
            }
            total += n;
        }
    }
    return total;
}

/// Input: `width`, `height`, `max_iter` as little-endian u32.
pub fn run(data: []const u8) u64 {
    if (data.len < 12) return mandelbrot(0, 0, 0);
    const width = std.mem.readInt(u32, data[0..4], .little);
    const height = std.mem.readInt(u32, data[4..8], .little);
    const max_iter = std.mem.readInt(u32, data[8..12], .little);
    return mandelbrot(width, height, max_iter);
}

pub fn digest() u64 {
    return 0;
}
