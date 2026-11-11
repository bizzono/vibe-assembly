/* utf8_validate kernel (C): the reference implementation itself. */
#include "../../../tasks/utf8_validate/ref.c"

uint64_t run(const uint8_t *data, size_t len) { return utf8_validate(data, len); }
uint64_t digest(void) { return 0; }
