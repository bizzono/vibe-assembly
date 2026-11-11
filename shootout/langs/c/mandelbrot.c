/* mandelbrot kernel (C): the reference implementation itself. Build with -ffp-contract=off. */
#include <stddef.h>
#include <string.h>
#include "../../../tasks/mandelbrot/ref.c"

uint64_t run(const uint8_t *data, size_t len) {
    uint32_t p[3] = {0, 0, 0};
    if (len >= 12) memcpy(p, data, 12);
    return mandelbrot(p[0], p[1], p[2]);
}
uint64_t digest(void) { return 0; }
