/* base64_encode -- input generators. */
#include "va_kit.h"

static const char *names[] = {"random", "zeros", "ones", "counting", "text"};

unsigned va_flavors(void) { return 5; }
const char *va_flavor_name(unsigned f) { return names[f]; }

size_t va_out_cap(size_t len) { return 4 * ((len + 2) / 3); }

void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor) {
    switch (flavor) {
    case 0: va_fill_random(r, buf, len); break;
    case 1: memset(buf, 0x00, len); break;
    case 2: memset(buf, 0xFF, len); break;
    case 3: /* every 6-bit value shows up in every position */
        for (size_t i = 0; i < len; i++) buf[i] = (uint8_t)(i * 7 + (i >> 8));
        break;
    default:
        for (size_t i = 0; i < len; i++) buf[i] = (uint8_t)(' ' + va_below(r, 95));
        break;
    }
}
