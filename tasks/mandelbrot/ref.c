/* mandelbrot -- reference implementation (the oracle). See SPEC.md.
 * Compile with -ffp-contract=off: the contract forbids fused multiply-add. */
#include <stdint.h>

uint64_t mandelbrot(uint64_t width, uint64_t height, uint64_t max_iter) {
    uint64_t total = 0;
    if (width == 0 || height == 0) return 0;
    double dx = 3.0 / (double)width;
    double dy = 3.0 / (double)height;
    for (uint64_t py = 0; py < height; py++) {
        double ci = -1.5 + (double)py * dy;
        for (uint64_t px = 0; px < width; px++) {
            double cr = -2.0 + (double)px * dx;
            double zr = 0.0, zi = 0.0;
            uint64_t n = 0;
            while (n < max_iter) {
                double zr2 = zr * zr;
                double zi2 = zi * zi;
                if (zr2 + zi2 > 4.0) break;
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
                n++;
            }
            total += n;
        }
    }
    return total;
}
