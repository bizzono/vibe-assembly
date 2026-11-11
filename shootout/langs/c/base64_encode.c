/* base64_encode kernel (C): the reference implementation itself. */
#include <stdlib.h>
#include "../../../tasks/base64_encode/ref.c"

static uint8_t *out;
static size_t out_len;

uint64_t run(const uint8_t *data, size_t len) {
    if (!out) out = malloc(4 * ((len + 2) / 3) + 1);
    out_len = base64_encode(data, len, out);
    return out_len;
}

uint64_t digest(void) {
    uint64_t h = 0xcbf29ce484222325ull;
    for (size_t i = 0; i < out_len; i++) h = (h ^ out[i]) * 0x100000001b3ull;
    return h;
}
