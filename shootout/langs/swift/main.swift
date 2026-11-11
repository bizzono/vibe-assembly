// Shootout driver (Swift). See shootout/PROTOCOL.md.
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#elseif canImport(Musl)
import Musl
#endif

func fail(_ message: String, status: Int32) -> Never {
    fputs(message + "\n", stderr)
    exit(status)
}

/// Reads the whole file into memory. Returns nil if it cannot be read.
func readFile(_ path: String) -> [UInt8]? {
    guard let f = fopen(path, "rb") else { return nil }
    defer { fclose(f) }
    guard fseek(f, 0, SEEK_END) == 0 else { return nil }
    let len = ftell(f)
    guard len >= 0, fseek(f, 0, SEEK_SET) == 0 else { return nil }
    if len == 0 { return [] }
    let bytes = [UInt8](unsafeUninitializedCapacity: len) { buffer, initializedCount in
        initializedCount = fread(buffer.baseAddress, 1, len, f)
    }
    return bytes.count == len ? bytes : nil
}

/// Nanoseconds in a `Duration` measured by the monotonic `ContinuousClock`.
func nanoseconds(_ d: Duration) -> UInt64 {
    let (seconds, attoseconds) = d.components
    return UInt64(seconds) * 1_000_000_000 + UInt64(attoseconds / 1_000_000_000)
}

func main() {
    let args = CommandLine.arguments
    guard args.count == 3, let minMs = UInt64(args[2]) else {
        fail("usage: \(args.first ?? "prog") <input-file> <min_ms>", status: 2)
    }
    guard let data = readFile(args[1]) else {
        fail("\(args[1]): read failed", status: 2)
    }
    let minNs = minMs &* 1_000_000
    let clock = ContinuousClock()

    data.withUnsafeBufferPointer { bytes in
        if minNs == 0 {  // cold mode: one call, no digest
            let t0 = clock.now
            let result = run(bytes)
            let best = nanoseconds(clock.now - t0)
            print("RESULT \(result) 0 \(best) 1")
            return
        }

        let warm = run(bytes)
        var result: UInt64 = 0
        var best = UInt64.max
        var total: UInt64 = 0
        var calls: UInt64 = 0
        while calls < 3 || (total < minNs && calls < 1_000_000) {
            let t0 = clock.now
            result = run(bytes)
            let dt = nanoseconds(clock.now - t0)
            if result != warm { fail("result changed between calls", status: 3) }
            best = min(best, dt)
            total += dt
            calls += 1
        }
        print("RESULT \(result) \(digest()) \(best) \(calls)")
    }
}

main()
