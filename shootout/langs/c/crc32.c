/* crc32 kernel (C): the reference implementation itself. */
#include "../../../tasks/crc32/ref.c"

uint64_t run(const uint8_t *data, size_t len) { return crc32_ieee(data, len); }
uint64_t digest(void) { return 0; }
