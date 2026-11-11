/* mandelbrot -- argument generators. Kept small: the reference is called thousands of times. */
#include "va_kit.h"

static const char *names[] = {"general", "tiny", "one-row", "few-iterations", "odd-widths"};

unsigned va_flavors(void) { return 5; }
const char *va_flavor_name(unsigned f) { return names[f]; }

void va_gen_args(va_rng *r, uint64_t a[4], unsigned flavor) {
    switch (flavor) {
    case 0: a[0] = va_range(r, 0, 48); a[1] = va_range(r, 0, 48); a[2] = va_range(r, 0, 150); break;
    case 1: a[0] = va_range(r, 0, 5); a[1] = va_range(r, 0, 5); a[2] = va_range(r, 0, 300); break;
    case 2: a[0] = va_range(r, 1, 400); a[1] = va_range(r, 1, 2); a[2] = va_range(r, 1, 120); break;
    case 3: a[0] = va_range(r, 1, 64); a[1] = va_range(r, 1, 64); a[2] = va_range(r, 0, 3); break;
    default: /* widths just around multiples of 2, 4, 8 and 16: vector tails */
        a[0] = 8 * va_range(r, 0, 8) + va_range(r, 0, 9);
        a[1] = va_range(r, 1, 12);
        a[2] = va_range(r, 1, 200);
        break;
    }
}
