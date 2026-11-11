'use strict';
// crc32 kernel (JavaScript): port of tasks/crc32/ref.c, the textbook table-driven
// CRC-32 with one table lookup per input byte.

// The 256-entry table for the reflected polynomial 0xEDB88320 (the same values as the
// literal table in ref.c), built once when the module is loaded.
const CRC_TABLE = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) {
    c = (c & 1) !== 0 ? (0xedb88320 ^ (c >>> 1)) >>> 0 : c >>> 1;
  }
  CRC_TABLE[n] = c;
}

function run(data) {
  const table = CRC_TABLE;
  const len = data.length;
  let crc = 0xffffffff;
  for (let i = 0; i < len; i++) {
    crc = (table[(crc ^ data[i]) & 0xff] ^ (crc >>> 8)) >>> 0;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function digest() {
  return 0n;
}

module.exports = { run, digest };
