//! Shootout driver (Zig). See shootout/PROTOCOL.md.
const std = @import("std");
const kernel = @import("kernel.zig");

const Io = std.Io;

/// Monotonic clock: CLOCK_UPTIME_RAW on macOS, CLOCK_MONOTONIC on Linux.
const clock: Io.Clock = .awake;

const max_calls = 1_000_000;

fn elapsedNs(io: Io, since: Io.Timestamp) u64 {
    return @intCast(since.durationTo(clock.now(io)).nanoseconds);
}

pub fn main(init: std.process.Init) !u8 {
    const io = init.io;

    const args = try init.minimal.args.toSlice(init.arena.allocator());
    if (args.len != 3) {
        std.debug.print("usage: {s} <input-file> <min_ms>\n", .{if (args.len > 0) args[0] else "prog"});
        return 2;
    }
    const data = Io.Dir.cwd().readFileAlloc(io, args[1], init.gpa, .unlimited) catch |err| {
        std.debug.print("{s}: {t}\n", .{ args[1], err });
        return 2;
    };
    defer init.gpa.free(data);
    const min_ms = std.fmt.parseInt(u64, args[2], 10) catch {
        std.debug.print("bad min_ms: {s}\n", .{args[2]});
        return 2;
    };
    const min_ns = min_ms *| std.time.ns_per_ms;

    var stdout_buffer: [128]u8 = undefined;
    var stdout_writer = Io.File.stdout().writerStreaming(io, &stdout_buffer);
    const stdout = &stdout_writer.interface;

    if (min_ms == 0) { // cold mode: one call, no digest
        const t0 = clock.now(io);
        const result = kernel.run(data);
        const dt = elapsedNs(io, t0);
        try stdout.print("RESULT {d} 0 {d} 1\n", .{ result, dt });
        try stdout.flush();
        return 0;
    }

    const warm = kernel.run(data);
    var result = warm;
    var best: u64 = std.math.maxInt(u64);
    var total: u64 = 0;
    var calls: u64 = 0;
    while (calls < 3 or (total < min_ns and calls < max_calls)) {
        const t0 = clock.now(io);
        result = kernel.run(data);
        const dt = elapsedNs(io, t0);
        if (result != warm) {
            std.debug.print("result changed between calls\n", .{});
            return 3;
        }
        best = @min(best, dt);
        total += dt;
        calls += 1;
    }

    const digest = kernel.digest();
    try stdout.print("RESULT {d} {d} {d} {d}\n", .{ result, digest, best, calls });
    try stdout.flush();
    return 0;
}
