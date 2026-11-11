/* wordcount kernel (C): the reference implementation itself. */
#include "../../../tasks/wordcount/ref.c"

uint64_t run(const uint8_t *data, size_t len) { return wordcount(data, len); }
uint64_t digest(void) { return 0; }
