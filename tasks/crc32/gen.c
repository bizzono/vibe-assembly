/* crc32 -- input generators. */
#include "va_kit.h"

static const char *names[] = {"random", "zeros", "ones", "text", "sparse"};

unsigned va_flavors(void) { return 5; }
const char *va_flavor_name(unsigned f) { return names[f]; }

void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor) {
    switch (flavor) {
    case 0: va_fill_random(r, buf, len); break;
    case 1: memset(buf, 0x00, len); break;
    case 2: memset(buf, 0xFF, len); break;
    case 3:
        for (size_t i = 0; i < len; i++) buf[i] = (uint8_t)(' ' + va_below(r, 95));
        break;
    default: /* mostly zero with a few set bits: exercises carry-less folding constants */
        memset(buf, 0, len);
        for (size_t k = 0; k < len / 97 + 1 && len; k++)
            buf[va_below(r, len)] = (uint8_t)(1u << va_below(r, 8));
        break;
    }
}
