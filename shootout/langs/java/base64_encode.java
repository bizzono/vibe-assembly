/* base64_encode kernel (Java): a port of tasks/base64_encode/ref.c. */
import java.nio.charset.StandardCharsets;

final class Kernel {
    private Kernel() {}

    private static final byte[] ALPHABET =
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".getBytes(StandardCharsets.US_ASCII);

    private static byte[] out; /* allocated on the first call, then reused */
    private static int outLen;

    private static int encode(byte[] src, byte[] dst) {
        final int len = src.length;
        int i = 0, o = 0;
        for (; i + 3 <= len; i += 3) {
            int v = (src[i] & 0xFF) << 16 | (src[i + 1] & 0xFF) << 8 | (src[i + 2] & 0xFF);
            dst[o++] = ALPHABET[v >>> 18];
            dst[o++] = ALPHABET[(v >>> 12) & 63];
            dst[o++] = ALPHABET[(v >>> 6) & 63];
            dst[o++] = ALPHABET[v & 63];
        }
        if (len - i == 1) {
            int v = (src[i] & 0xFF) << 16;
            dst[o++] = ALPHABET[v >>> 18];
            dst[o++] = ALPHABET[(v >>> 12) & 63];
            dst[o++] = '=';
            dst[o++] = '=';
        } else if (len - i == 2) {
            int v = (src[i] & 0xFF) << 16 | (src[i + 1] & 0xFF) << 8;
            dst[o++] = ALPHABET[v >>> 18];
            dst[o++] = ALPHABET[(v >>> 12) & 63];
            dst[o++] = ALPHABET[(v >>> 6) & 63];
            dst[o++] = '=';
        }
        return o;
    }

    static long run(byte[] data) {
        if (out == null) out = new byte[4 * ((data.length + 2) / 3)];
        outLen = encode(data, out);
        return outLen;
    }

    /* 64-bit FNV-1a of the bytes written by the last run(). */
    static long digest() {
        long h = 0xcbf29ce484222325L;
        for (int i = 0; i < outLen; i++) {
            h = (h ^ (out[i] & 0xFF)) * 0x100000001b3L;
        }
        return h;
    }
}
