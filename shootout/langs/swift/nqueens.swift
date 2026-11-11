// nqueens kernel (Swift): port of tasks/nqueens/ref.c, the textbook bitmask
// backtracking search.

private func place(_ all: UInt32, _ cols: UInt32, _ diagL: UInt32, _ diagR: UInt32) -> UInt64 {
    if cols == all { return 1 }
    var count: UInt64 = 0
    var free = all & ~(cols | diagL | diagR)
    while free != 0 {
        let bit = free & (0 &- free)  // lowest free square in this row
        free ^= bit
        count &+= place(all, cols | bit, (diagL | bit) << 1, (diagR | bit) >> 1)
    }
    return count
}

func nqueens(_ n: UInt64) -> UInt64 {
    if n > 31 { return 0 }
    let all = UInt32((UInt64(1) << n) - 1)
    return place(all, 0, 0, 0)
}

// The input is n as a little-endian UInt32.
func run(_ data: UnsafeBufferPointer<UInt8>) -> UInt64 {
    var n: UInt32 = 0
    if data.count >= 4 {
        let raw = UnsafeRawBufferPointer(data)
        n = UInt32(littleEndian: raw.loadUnaligned(fromByteOffset: 0, as: UInt32.self))
    }
    return nqueens(UInt64(n))
}

func digest() -> UInt64 { return 0 }
