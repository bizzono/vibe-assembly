'use strict';
// base64_encode kernel (JavaScript): port of tasks/base64_encode/ref.c.

const ALPHABET = new Uint8Array(64);
{
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  for (let k = 0; k < 64; k++) ALPHABET[k] = chars.charCodeAt(k);
}
const PAD = 0x3d; // '='

let out = null; // allocated on the first call, then reused
let outLen = 0;

function encode(src, dst) {
  const alphabet = ALPHABET;
  const len = src.length;
  let i = 0;
  let o = 0;
  for (; i + 3 <= len; i += 3) {
    const v = (src[i] << 16) | (src[i + 1] << 8) | src[i + 2];
    dst[o++] = alphabet[v >> 18];
    dst[o++] = alphabet[(v >> 12) & 63];
    dst[o++] = alphabet[(v >> 6) & 63];
    dst[o++] = alphabet[v & 63];
  }
  if (len - i === 1) {
    const v = src[i] << 16;
    dst[o++] = alphabet[v >> 18];
    dst[o++] = alphabet[(v >> 12) & 63];
    dst[o++] = PAD;
    dst[o++] = PAD;
  } else if (len - i === 2) {
    const v = (src[i] << 16) | (src[i + 1] << 8);
    dst[o++] = alphabet[v >> 18];
    dst[o++] = alphabet[(v >> 12) & 63];
    dst[o++] = alphabet[(v >> 6) & 63];
    dst[o++] = PAD;
  }
  return o;
}

function run(data) {
  if (out === null) out = new Uint8Array(4 * Math.floor((data.length + 2) / 3));
  outLen = encode(data, out);
  return outLen;
}

// 64-bit FNV-1a of the bytes written by the last run. Not timed. The hash is kept as two
// unsigned 32-bit halves; multiplying by the prime 0x100000001b3 = 2^40 + 0x1b3 is
// h * 0x1b3 + (h << 40), and every intermediate below stays under 2^53, so it is exact.
function digest() {
  let hi = 0xcbf29ce4;
  let lo = 0x84222325;
  for (let i = 0; i < outLen; i++) {
    lo = (lo ^ out[i]) >>> 0;
    const t = lo * 0x1b3;
    hi = (hi * 0x1b3 + Math.floor(t / 0x100000000) + ((lo << 8) >>> 0)) >>> 0;
    lo = t >>> 0;
  }
  return (BigInt(hi) << 32n) | BigInt(lo);
}

module.exports = { run, digest };
