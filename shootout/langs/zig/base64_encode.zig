//! base64_encode kernel (Zig): port of tasks/base64_encode/ref.c.
const std = @import("std");

const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Writes the Base64 encoding of `src` to `dst` and returns the number of bytes written.
fn base64Encode(src: []const u8, dst: []u8) usize {
    const len = src.len;
    var i: usize = 0;
    var o: usize = 0;
    while (i + 3 <= len) : (i += 3) {
        const v = @as(u32, src[i]) << 16 | @as(u32, src[i + 1]) << 8 | src[i + 2];
        dst[o] = alphabet[v >> 18];
        dst[o + 1] = alphabet[(v >> 12) & 63];
        dst[o + 2] = alphabet[(v >> 6) & 63];
        dst[o + 3] = alphabet[v & 63];
        o += 4;
    }
    if (len - i == 1) {
        const v = @as(u32, src[i]) << 16;
        dst[o] = alphabet[v >> 18];
        dst[o + 1] = alphabet[(v >> 12) & 63];
        dst[o + 2] = '=';
        dst[o + 3] = '=';
        o += 4;
    } else if (len - i == 2) {
        const v = @as(u32, src[i]) << 16 | @as(u32, src[i + 1]) << 8;
        dst[o] = alphabet[v >> 18];
        dst[o + 1] = alphabet[(v >> 12) & 63];
        dst[o + 2] = alphabet[(v >> 6) & 63];
        dst[o + 3] = '=';
        o += 4;
    }
    return o;
}

/// Output buffer: allocated once, on the first call to `run`, then reused.
var out: ?[]u8 = null;
var out_len: usize = 0;

pub fn run(data: []const u8) u64 {
    const dst = out orelse blk: {
        const buf = std.heap.page_allocator.alloc(u8, 4 * ((data.len + 2) / 3)) catch @panic("out of memory");
        out = buf;
        break :blk buf;
    };
    out_len = base64Encode(data, dst);
    return out_len;
}

/// 64-bit FNV-1a of the bytes written by the last `run`.
pub fn digest() u64 {
    var h: u64 = 0xcbf29ce484222325;
    const buf = out orelse return h;
    for (buf[0..out_len]) |b| {
        h = (h ^ b) *% 0x100000001b3;
    }
    return h;
}
