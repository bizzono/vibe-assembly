'use strict';
// utf8_validate kernel (JavaScript): port of tasks/utf8_validate/ref.c, a direct
// transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.

function inRange(c, lo, hi) {
  return c >= lo && c <= hi;
}

function run(s) {
  const n = s.length;
  let i = 0;
  while (i < n) {
    const c = s[i];
    if (c < 0x80) {
      i += 1;
    } else if (inRange(c, 0xc2, 0xdf)) {
      if (n - i < 2 || !inRange(s[i + 1], 0x80, 0xbf)) return 0;
      i += 2;
    } else if (inRange(c, 0xe0, 0xef)) {
      const lo = c === 0xe0 ? 0xa0 : 0x80; // E0: no overlong encodings
      const hi = c === 0xed ? 0x9f : 0xbf; // ED: no UTF-16 surrogates
      if (n - i < 3 || !inRange(s[i + 1], lo, hi) || !inRange(s[i + 2], 0x80, 0xbf)) return 0;
      i += 3;
    } else if (inRange(c, 0xf0, 0xf4)) {
      const lo = c === 0xf0 ? 0x90 : 0x80; // F0: no overlong encodings
      const hi = c === 0xf4 ? 0x8f : 0xbf; // F4: nothing above U+10FFFF
      if (n - i < 4 || !inRange(s[i + 1], lo, hi) || !inRange(s[i + 2], 0x80, 0xbf) ||
          !inRange(s[i + 3], 0x80, 0xbf)) {
        return 0;
      }
      i += 4;
    } else {
      return 0; // 80..C1 and F5..FF never start a sequence
    }
  }
  return 1;
}

function digest() {
  return 0n;
}

module.exports = { run, digest };
