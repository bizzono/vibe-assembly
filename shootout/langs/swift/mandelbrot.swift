// mandelbrot kernel (Swift): port of tasks/mandelbrot/ref.c.
//
// The result must be bit-exact, so no fused multiply-add is allowed. Swift never
// fuses `a * b + c` on its own (that takes an explicit `addingProduct`), so the plain
// operators below are each their own correctly-rounded IEEE-754 operation.

func mandelbrot(_ width: UInt64, _ height: UInt64, _ maxIter: UInt64) -> UInt64 {
    var total: UInt64 = 0
    if width == 0 || height == 0 { return 0 }
    let dx = 3.0 / Double(width)
    let dy = 3.0 / Double(height)
    for py in 0..<height {
        let ci = -1.5 + Double(py) * dy
        for px in 0..<width {
            let cr = -2.0 + Double(px) * dx
            var zr = 0.0
            var zi = 0.0
            var n: UInt64 = 0
            while n < maxIter {
                let zr2 = zr * zr
                let zi2 = zi * zi
                if zr2 + zi2 > 4.0 { break }
                zi = 2.0 * zr * zi + ci
                zr = zr2 - zi2 + cr
                n &+= 1
            }
            total &+= n
        }
    }
    return total
}

/// The little-endian UInt32 at byte offset `offset`.
private func littleEndianUInt32(_ data: UnsafeBufferPointer<UInt8>, at offset: Int) -> UInt32 {
    let raw = UnsafeRawBufferPointer(data)
    return UInt32(littleEndian: raw.loadUnaligned(fromByteOffset: offset, as: UInt32.self))
}

// The input is width, height, max_iter as little-endian UInt32.
func run(_ data: UnsafeBufferPointer<UInt8>) -> UInt64 {
    guard data.count >= 12 else { return mandelbrot(0, 0, 0) }
    return mandelbrot(
        UInt64(littleEndianUInt32(data, at: 0)),
        UInt64(littleEndianUInt32(data, at: 4)),
        UInt64(littleEndianUInt32(data, at: 8)))
}

func digest() -> UInt64 { return 0 }
