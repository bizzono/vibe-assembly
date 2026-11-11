# crc32

```c
uint64_t crc32_ieee(const uint8_t *buf, size_t len);
```

Return the CRC-32 of `buf[0 .. len)` -- the checksum used by zlib, gzip, PNG and
Ethernet (CRC-32/ISO-HDLC). The 32-bit value is returned zero-extended to 64 bits.

Parameters of the CRC: polynomial `0x04C11DB7` (reflected form `0xEDB88320`), initial
value `0xFFFFFFFF`, input and output reflected, final XOR `0xFFFFFFFF`.

Check value: the CRC-32 of the nine ASCII bytes `123456789` is `0xCBF43926`.
The CRC-32 of the empty buffer is `0`.

- `len` may be 0. The input is arbitrary bytes.
- This is **not** CRC-32C (Castagnoli); the polynomial matters.
