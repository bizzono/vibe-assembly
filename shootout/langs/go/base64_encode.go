// base64_encode kernel (Go): port of tasks/base64_encode/ref.c.
package main

const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

// base64Encode writes the Base64 text of src to dst and returns the number of
// bytes written. dst must have room for 4*ceil(len(src)/3) bytes.
func base64Encode(src, dst []byte) int {
	i, o := 0, 0
	// Same loop as the reference (which tests i+3 <= len). Each group is
	// re-sliced once, so there is one bounds check per group instead of seven.
	for ; i <= len(src)-3; i += 3 {
		s := src[i : i+3]
		d := dst[o : o+4]
		v := uint32(s[0])<<16 | uint32(s[1])<<8 | uint32(s[2])
		d[0] = alphabet[v>>18]
		d[1] = alphabet[(v>>12)&63]
		d[2] = alphabet[(v>>6)&63]
		d[3] = alphabet[v&63]
		o += 4
	}
	if len(src)-i == 1 {
		v := uint32(src[i]) << 16
		dst[o] = alphabet[v>>18]
		dst[o+1] = alphabet[(v>>12)&63]
		dst[o+2] = '='
		dst[o+3] = '='
		o += 4
	} else if len(src)-i == 2 {
		v := uint32(src[i])<<16 | uint32(src[i+1])<<8
		dst[o] = alphabet[v>>18]
		dst[o+1] = alphabet[(v>>12)&63]
		dst[o+2] = alphabet[(v>>6)&63]
		dst[o+3] = '='
		o += 4
	}
	return o
}

// The output buffer is allocated on the first call and reused after that.
var (
	out    []byte
	outLen int
)

func run(data []byte) uint64 {
	if out == nil {
		out = make([]byte, 4*((len(data)+2)/3))
	}
	outLen = base64Encode(data, out)
	return uint64(outLen)
}

// digest is the 64-bit FNV-1a hash of the bytes the last run wrote.
func digest() uint64 {
	h := uint64(0xcbf29ce484222325)
	for _, b := range out[:outLen] {
		h = (h ^ uint64(b)) * 0x100000001b3
	}
	return h
}
