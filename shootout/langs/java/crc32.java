/* crc32 kernel (Java): a port of tasks/crc32/ref.c, the textbook table-driven CRC-32
 * (one table lookup per input byte). The table is built once, when the class is loaded. */
final class Kernel {
    private Kernel() {}

    private static final int[] TABLE = makeTable();

    private static int[] makeTable() {
        int[] table = new int[256];
        for (int n = 0; n < 256; n++) {
            int c = n;
            for (int k = 0; k < 8; k++) {
                c = (c & 1) != 0 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
            }
            table[n] = c;
        }
        return table;
    }

    static long run(byte[] data) {
        int crc = 0xFFFFFFFF;
        for (byte b : data) {
            crc = TABLE[(crc ^ b) & 0xFF] ^ (crc >>> 8);
        }
        return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFFL; /* zero-extend to 64 bits */
    }

    static long digest() {
        return 0;
    }
}
