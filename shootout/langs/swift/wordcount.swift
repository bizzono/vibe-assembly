// wordcount kernel (Swift): port of tasks/wordcount/ref.c.

@inline(__always)
private func isSpace(_ c: UInt8) -> Bool {
    // space, \t \n \v \f \r
    return c == UInt8(ascii: " ") || (c >= UInt8(ascii: "\t") && c <= UInt8(ascii: "\r"))
}

func wordcount(_ buf: UnsafeBufferPointer<UInt8>) -> UInt64 {
    var words: UInt64 = 0
    var inWord = false
    for c in buf {
        if isSpace(c) {
            inWord = false
        } else if !inWord {
            inWord = true
            words &+= 1
        }
    }
    return words
}

func run(_ data: UnsafeBufferPointer<UInt8>) -> UInt64 { return wordcount(data) }
func digest() -> UInt64 { return 0 }
