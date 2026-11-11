'use strict';
// nqueens kernel (JavaScript): port of tasks/nqueens/ref.c, the textbook bitmask
// backtracking search. All masks are 32-bit integers, as in the reference.

function place(all, cols, diagL, diagR) {
  if (cols === all) return 1;
  let count = 0;
  let free = all & ~(cols | diagL | diagR);
  while (free !== 0) {
    const bit = free & -free; // lowest free square in this row
    free ^= bit;
    count += place(all, cols | bit, (diagL | bit) << 1, (diagR | bit) >>> 1);
  }
  return count;
}

function nqueens(n) {
  if (n > 31) return 0;
  const all = 2 ** n - 1; // n low bits set; at most 2^31 - 1
  return place(all, 0, 0, 0);
}

// The input is n as a little-endian u32.
function run(data) {
  if (data.length < 4) return nqueens(0);
  const params = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return nqueens(params.getUint32(0, true));
}

function digest() {
  return 0n;
}

module.exports = { run, digest };
