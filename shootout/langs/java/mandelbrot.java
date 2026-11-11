/* mandelbrot kernel (Java): a port of tasks/mandelbrot/ref.c. Java doubles are strict
 * IEEE-754 binary64 and the JIT never fuses a multiply and an add, as the contract needs. */
final class Kernel {
    private Kernel() {}

    /* The parameters are unsigned 32-bit values; Java has no unsigned int, so use long. */
    private static long mandelbrot(long width, long height, long maxIter) {
        long total = 0;
        if (width == 0 || height == 0) return 0;
        double dx = 3.0 / (double) width;
        double dy = 3.0 / (double) height;
        for (long py = 0; py < height; py++) {
            double ci = -1.5 + (double) py * dy;
            for (long px = 0; px < width; px++) {
                double cr = -2.0 + (double) px * dx;
                double zr = 0.0, zi = 0.0;
                long n = 0;
                while (n < maxIter) {
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

    private static long u32le(byte[] d, int at) {
        return (d[at] & 0xFFL) | (d[at + 1] & 0xFFL) << 8 | (d[at + 2] & 0xFFL) << 16 | (d[at + 3] & 0xFFL) << 24;
    }

    static long run(byte[] data) {
        long width = 0, height = 0, maxIter = 0;
        if (data.length >= 12) {
            width = u32le(data, 0);
            height = u32le(data, 4);
            maxIter = u32le(data, 8);
        }
        return mandelbrot(width, height, maxIter);
    }

    static long digest() {
        return 0;
    }
}
