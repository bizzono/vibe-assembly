// nqueens kernel (Go): port of tasks/nqueens/ref.c, the textbook bitmask
// backtracking search.
package main

import "encoding/binary"

func place(all, cols, diagL, diagR uint32) uint64 {
	if cols == all {
		return 1
	}
	var count uint64
	free := all &^ (cols | diagL | diagR)
	for free != 0 {
		bit := free & -free // lowest free square in this row
		free ^= bit
		count += place(all, cols|bit, (diagL|bit)<<1, (diagR|bit)>>1)
	}
	return count
}

func nqueens(n uint64) uint64 {
	if n > 31 {
		return 0
	}
	all := uint32(uint64(1)<<n - 1)
	return place(all, 0, 0, 0)
}

// The input is n as a little-endian uint32.
func run(data []byte) uint64 {
	var n uint32
	if len(data) >= 4 {
		n = binary.LittleEndian.Uint32(data)
	}
	return nqueens(uint64(n))
}

func digest() uint64 { return 0 }
