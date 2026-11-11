'use strict';
// Shootout driver (JavaScript, Node.js). See shootout/PROTOCOL.md.
//
//   node main.js <kernel.js> <input-file> <min_ms>
//
// The kernel is a CommonJS module exporting run(data: Uint8Array) and digest().

const fs = require('fs');
const path = require('path');

function main(argv) {
  if (argv.length !== 3) {
    process.stderr.write('usage: node main.js <kernel.js> <input-file> <min_ms>\n');
    return 2;
  }
  const kernel = require(path.resolve(argv[0]));
  const run = kernel.run;

  // A plain Uint8Array over the bytes that were read (Buffer is a subclass of it).
  const file = fs.readFileSync(argv[1]);
  const data = new Uint8Array(file.buffer, file.byteOffset, file.byteLength);
  const minNs = BigInt(argv[2]) * 1000000n;
  const now = process.hrtime.bigint;

  if (minNs === 0n) { // cold mode: one call, no digest
    const t0 = now();
    const result = run(data);
    const dt = now() - t0;
    process.stdout.write(`RESULT ${BigInt(result)} 0 ${dt} 1\n`);
    return 0;
  }

  const warm = run(data);
  let result = warm;
  let best = -1n;
  let total = 0n;
  let calls = 0;
  while (calls < 3 || (total < minNs && calls < 1000000)) {
    const t0 = now();
    result = run(data);
    const dt = now() - t0;
    if (result !== warm) {
      process.stderr.write('result changed between calls\n');
      return 3;
    }
    if (best < 0n || dt < best) best = dt;
    total += dt;
    calls++;
  }
  const digest = BigInt.asUintN(64, BigInt(kernel.digest()));
  process.stdout.write(`RESULT ${BigInt(result)} ${digest} ${best} ${calls}\n`);
  return 0;
}

process.exitCode = main(process.argv.slice(2));
