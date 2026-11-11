# utf8_validate

```c
uint64_t utf8_validate(const uint8_t *buf, size_t len);
```

Return `1` if `buf[0 .. len)` is well-formed UTF-8, `0` if it is not.

"Well-formed" is exactly the definition in the Unicode Standard (Table 3-7) and
RFC 3629. Every byte must belong to one of these sequences:

| first byte | second     | third      | fourth     |
|------------|------------|------------|------------|
| `00..7F`   |            |            |            |
| `C2..DF`   | `80..BF`   |            |            |
| `E0`       | `A0..BF`   | `80..BF`   |            |
| `E1..EC`   | `80..BF`   | `80..BF`   |            |
| `ED`       | `80..9F`   | `80..BF`   |            |
| `EE..EF`   | `80..BF`   | `80..BF`   |            |
| `F0`       | `90..BF`   | `80..BF`   | `80..BF`   |
| `F1..F3`   | `80..BF`   | `80..BF`   | `80..BF`   |
| `F4`       | `80..8F`   | `80..BF`   | `80..BF`   |

So the following are all **invalid**: bytes `C0`, `C1`, `F5..FF` anywhere; a
continuation byte (`80..BF`) that does not follow a lead byte; overlong encodings
(`E0 80..9F`, `F0 80..8F`); UTF-16 surrogates (`ED A0..BF`); code points above
U+10FFFF (`F4 90..BF`); and a sequence cut short by the end of the buffer.

- The empty buffer is valid (return `1`). `0x00` is an ordinary valid byte.
- The return value must be exactly `1` or `0`.
