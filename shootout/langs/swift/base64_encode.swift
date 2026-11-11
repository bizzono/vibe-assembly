// base64_encode kernel (Swift): port of tasks/base64_encode/ref.c.

// A StaticString is a pointer to constant bytes in the binary, like the reference's
// `static const char alphabet[]`.
private let alphabet: StaticString =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
private let pad = UInt8(ascii: "=")

/// Writes the Base64 text of `src` to `dst` and returns the number of bytes written.
/// `dst` must have room for 4 * ceil(src.count / 3) bytes.
func base64Encode(_ src: UnsafeBufferPointer<UInt8>, _ dst: UnsafeMutableBufferPointer<UInt8>) -> Int {
    let table = alphabet.utf8Start
    let len = src.count
    var i = 0
    var o = 0
    while i &+ 3 <= len {
        let v = UInt32(src[i]) << 16 | UInt32(src[i &+ 1]) << 8 | UInt32(src[i &+ 2])
        dst[o] = table[Int(v >> 18)]
        dst[o &+ 1] = table[Int((v >> 12) & 63)]
        dst[o &+ 2] = table[Int((v >> 6) & 63)]
        dst[o &+ 3] = table[Int(v & 63)]
        o &+= 4
        i &+= 3
    }
    if len &- i == 1 {
        let v = UInt32(src[i]) << 16
        dst[o] = table[Int(v >> 18)]
        dst[o &+ 1] = table[Int((v >> 12) & 63)]
        dst[o &+ 2] = pad
        dst[o &+ 3] = pad
        o &+= 4
    } else if len &- i == 2 {
        let v = UInt32(src[i]) << 16 | UInt32(src[i &+ 1]) << 8
        dst[o] = table[Int(v >> 18)]
        dst[o &+ 1] = table[Int((v >> 12) & 63)]
        dst[o &+ 2] = table[Int((v >> 6) & 63)]
        dst[o &+ 3] = pad
        o &+= 4
    }
    return o
}

// The output buffer is allocated on the first call and reused after that.
private var out: [UInt8] = []
private var outLen = 0

func run(_ data: UnsafeBufferPointer<UInt8>) -> UInt64 {
    if out.isEmpty {
        let capacity = 4 * ((data.count + 2) / 3)
        out = [UInt8](unsafeUninitializedCapacity: capacity) { _, count in count = capacity }
    }
    outLen = out.withUnsafeMutableBufferPointer { base64Encode(data, $0) }
    return UInt64(outLen)
}

/// The 64-bit FNV-1a hash of the bytes the last `run` wrote.
func digest() -> UInt64 {
    var h: UInt64 = 0xcbf2_9ce4_8422_2325
    for byte in out[..<outLen] {
        h = (h ^ UInt64(byte)) &* 0x100_0000_01b3
    }
    return h
}
