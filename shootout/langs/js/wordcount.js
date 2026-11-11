'use strict';
// wordcount kernel (JavaScript): port of tasks/wordcount/ref.c.

function isSpace(c) {
  return c === 0x20 || (c >= 0x09 && c <= 0x0d); // space, \t \n \v \f \r
}

function run(data) {
  const len = data.length;
  let words = 0;
  let inWord = false;
  for (let i = 0; i < len; i++) {
    if (isSpace(data[i])) {
      inWord = false;
    } else if (!inWord) {
      inWord = true;
      words++;
    }
  }
  return words;
}

function digest() {
  return 0n;
}

module.exports = { run, digest };
