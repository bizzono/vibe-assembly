# base64_encode

```c
size_t base64_encode(const uint8_t *src, size_t len, uint8_t *dst);
```

Write the standard Base64 encoding (RFC 4648 section 4) of `src[0 .. len)` to `dst` and
return the number of bytes written, which is always `4 * ceil(len / 3)`.

- Alphabet: `A-Z a-z 0-9 + /`. The last group is padded with `=` (one `=` when
  `len % 3 == 2`, two when `len % 3 == 1`). No line breaks, no NUL terminator.
- Each 3 input bytes `a b c` form a 24-bit number `a<<16 | b<<8 | c`; its four 6-bit
  groups, most significant first, index the alphabet.
- `dst` has room for exactly `4 * ceil(len / 3)` bytes and not one byte more.
- `src` and `dst` do not overlap. `len` may be 0 (write nothing, return 0).

Example: the 5 bytes `hello` encode to the 8 bytes `aGVsbG8=`.
