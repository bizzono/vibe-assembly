//! crc32 kernel (Zig): port of tasks/crc32/ref.c.
//! The textbook table-driven CRC-32: one table lookup per input byte.

/// The same 256-entry table as the reference, computed at compile time from the
/// reflected polynomial 0xEDB88320.
const crc_table: [256]u32 = blk: {
    @setEvalBranchQuota(10_000);
    var table: [256]u32 = undefined;
    for (&table, 0..) |*entry, i| {
        var c: u32 = i;
        for (0..8) |_| {
            c = if (c & 1 != 0) (c >> 1) ^ 0xEDB88320 else c >> 1;
        }
        entry.* = c;
    }
    break :blk table;
};

fn crc32Ieee(buf: []const u8) u32 {
    var crc: u32 = 0xFFFFFFFF;
    for (buf) |byte| {
        crc = crc_table[(crc ^ byte) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFF;
}

pub fn run(data: []const u8) u64 {
    return crc32Ieee(data);
}

pub fn digest() u64 {
    return 0;
}
