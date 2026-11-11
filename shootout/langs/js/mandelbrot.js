'use strict';
// mandelbrot kernel (JavaScript): port of tasks/mandelbrot/ref.c.
// JavaScript numbers are IEEE-754 doubles and every * + - below is its own
// correctly-rounded operation (the language has no fused multiply-add), which is what
// the contract requires. The operation order is the reference's.

function mandelbrot(width, height, maxIter) {
  let total = 0; // exact while below 2^53
  if (width === 0 || height === 0) return 0;
  const dx = 3.0 / width;
  const dy = 3.0 / height;
  for (let py = 0; py < height; py++) {
    const ci = -1.5 + py * dy;
    for (let px = 0; px < width; px++) {
      const cr = -2.0 + px * dx;
      let zr = 0.0;
      let zi = 0.0;
      let n = 0;
      while (n < maxIter) {
        const zr2 = zr * zr;
        const zi2 = zi * zi;
        if (zr2 + zi2 > 4.0) break;
        zi = 2.0 * zr * zi + ci;
        zr = zr2 - zi2 + cr;
        n++;
      }
      total += n;
    }
  }
  return total;
}

// The input is width, height, max_iter as little-endian u32.
function run(data) {
  if (data.length < 12) return 0;
  const params = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return mandelbrot(params.getUint32(0, true), params.getUint32(4, true), params.getUint32(8, true));
}

function digest() {
  return 0n;
}

module.exports = { run, digest };
