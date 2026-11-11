/* nqueens -- argument generators. */
#include "va_kit.h"

static const char *names[] = {"n=0..8", "n=7..10"};

unsigned va_flavors(void) { return 2; }
const char *va_flavor_name(unsigned f) { return names[f]; }

void va_gen_args(va_rng *r, uint64_t a[4], unsigned flavor) {
    a[0] = flavor == 0 ? va_range(r, 0, 8) : va_range(r, 7, 10);
}
