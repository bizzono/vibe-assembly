// mandelbrot kernel (Go): port of tasks/mandelbrot/ref.c.
//
// The result must be bit-exact, so no fused multiply-add is allowed. The Go compiler
// may fuse x*y + z (and does on arm64); an explicit float64(...) conversion of the
// product rounds it and so forbids the fusion. Every product that feeds an add or a
// subtract below is wrapped that way.
package main

import "encoding/binary"

func mandelbrot(width, height, maxIter uint64) uint64 {
	var total uint64
	if width == 0 || height == 0 {
		return 0
	}
	dx := 3.0 / float64(width)
	dy := 3.0 / float64(height)
	for py := uint64(0); py < height; py++ {
		ci := -1.5 + float64(float64(py)*dy)
		for px := uint64(0); px < width; px++ {
			cr := -2.0 + float64(float64(px)*dx)
			zr, zi := 0.0, 0.0
			var n uint64
			for n < maxIter {
				zr2 := float64(zr * zr)
				zi2 := float64(zi * zi)
				if zr2+zi2 > 4.0 {
					break
				}
				zi = float64(2.0*zr*zi) + ci
				zr = zr2 - zi2 + cr
				n++
			}
			total += n
		}
	}
	return total
}

// The input is width, height, max_iter as little-endian uint32.
func run(data []byte) uint64 {
	var p [3]uint32
	if len(data) >= 12 {
		for i := range p {
			p[i] = binary.LittleEndian.Uint32(data[4*i:])
		}
	}
	return mandelbrot(uint64(p[0]), uint64(p[1]), uint64(p[2]))
}

func digest() uint64 { return 0 }
