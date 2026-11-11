// Shootout driver (Go). See shootout/PROTOCOL.md.
package main

import (
	"fmt"
	"math"
	"os"
	"strconv"
	"time"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintf(os.Stderr, "usage: %s <input-file> <min_ms>\n", os.Args[0])
		os.Exit(2)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	minMs, err := strconv.ParseUint(os.Args[2], 10, 64)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bad min_ms %q\n", os.Args[2])
		os.Exit(2)
	}
	minNs := minMs * 1_000_000

	// time.Now carries a monotonic clock reading and time.Since subtracts those.
	if minNs == 0 { // cold mode: one call, no digest
		t0 := time.Now()
		result := run(data)
		best := time.Since(t0).Nanoseconds()
		fmt.Printf("RESULT %d 0 %d 1\n", result, best)
		return
	}

	warm := run(data)
	var result, total, calls uint64
	best := uint64(math.MaxUint64)
	for calls < 3 || (total < minNs && calls < 1_000_000) {
		t0 := time.Now()
		result = run(data)
		dt := uint64(time.Since(t0).Nanoseconds())
		if result != warm {
			fmt.Fprintln(os.Stderr, "result changed between calls")
			os.Exit(3)
		}
		best = min(best, dt)
		total += dt
		calls++
	}
	fmt.Printf("RESULT %d %d %d %d\n", result, digest(), best, calls)
}
