// crc32 kernel (Go): port of tasks/crc32/ref.c, the textbook table-driven CRC-32
// (one table lookup per input byte).
package main

// crcTable holds the same 256 entries as the reference's table. It is filled in
// once during package initialization, before main (and so before any timed call).
var crcTable = func() (t [256]uint32) {
	for i := range t {
		c := uint32(i)
		for k := 0; k < 8; k++ {
			if c&1 != 0 {
				c = 0xEDB88320 ^ (c >> 1)
			} else {
				c >>= 1
			}
		}
		t[i] = c
	}
	return t
}()

func crc32IEEE(buf []byte) uint64 {
	crc := uint32(0xFFFFFFFF)
	for _, b := range buf {
		crc = crcTable[byte(crc)^b] ^ (crc >> 8)
	}
	return uint64(crc ^ 0xFFFFFFFF)
}

func run(data []byte) uint64 { return crc32IEEE(data) }
func digest() uint64         { return 0 }
