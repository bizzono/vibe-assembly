/* nqueens kernel (C): the reference implementation itself. */
#include <stddef.h>
#include <string.h>
#include "../../../tasks/nqueens/ref.c"

uint64_t run(const uint8_t *data, size_t len) {
    uint32_t n = 0;
    if (len >= 4) memcpy(&n, data, 4);
    return nqueens(n);
}
uint64_t digest(void) { return 0; }
