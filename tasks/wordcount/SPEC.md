# wordcount

```c
uint64_t wordcount(const uint8_t *buf, size_t len);
```

Return the number of words in `buf[0 .. len)`.

A **word** is a maximal run of non-whitespace bytes. **Whitespace** is exactly these six
byte values: space `0x20`, tab `0x09`, newline `0x0A`, vertical tab `0x0B`, form feed
`0x0C`, carriage return `0x0D`. Every other byte value, including `0x00` and every byte
`>= 0x80`, is part of a word.

Equivalently: the result is the number of positions `i` where `buf[i]` is not whitespace
and either `i == 0` or `buf[i-1]` is whitespace.

- `len` may be 0 (the result is 0). `buf` is not NUL-terminated.
- The input is arbitrary bytes, not necessarily text.
- `len` can be large (gigabytes); the count must not overflow or wrap.
