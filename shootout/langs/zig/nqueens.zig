//! nqueens kernel (Zig): port of tasks/nqueens/ref.c.
//! The textbook bitmask backtracking search.
const std = @import("std");

fn place(all: u32, cols: u32, diag_l: u32, diag_r: u32) u64 {
    if (cols == all) return 1;
    var count: u64 = 0;
    var free = all & ~(cols | diag_l | diag_r);
    while (free != 0) {
        const bit = free & -%free; // lowest free square in this row
        free ^= bit;
        count += place(all, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1);
    }
    return count;
}

fn nqueens(n: u64) u64 {
    if (n > 31) return 0;
    const all = (@as(u32, 1) << @as(u5, @intCast(n))) - 1;
    return place(all, 0, 0, 0);
}

/// Input: `n` as a little-endian u32.
pub fn run(data: []const u8) u64 {
    const n: u32 = if (data.len >= 4) std.mem.readInt(u32, data[0..4], .little) else 0;
    return nqueens(n);
}

pub fn digest() u64 {
    return 0;
}
