/* nqueens kernel (Java): a port of tasks/nqueens/ref.c, the textbook bitmask backtracking search. */
final class Kernel {
    private Kernel() {}

    private static long place(int all, int cols, int diagL, int diagR) {
        if (cols == all) return 1;
        long count = 0;
        int free = all & ~(cols | diagL | diagR);
        while (free != 0) {
            int bit = free & -free; /* lowest free square in this row */
            free ^= bit;
            count += place(all, cols | bit, (diagL | bit) << 1, (diagR | bit) >>> 1);
        }
        return count;
    }

    private static long nqueens(long n) {
        if (n > 31) return 0;
        int all = (int) ((1L << n) - 1);
        return place(all, 0, 0, 0);
    }

    static long run(byte[] data) {
        long n = 0; /* unsigned 32-bit, little-endian */
        if (data.length >= 4) {
            n = (data[0] & 0xFFL) | (data[1] & 0xFFL) << 8 | (data[2] & 0xFFL) << 16 | (data[3] & 0xFFL) << 24;
        }
        return nqueens(n);
    }

    static long digest() {
        return 0;
    }
}
