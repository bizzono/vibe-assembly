/* wordcount kernel (Java): a port of tasks/wordcount/ref.c. */
final class Kernel {
    private Kernel() {}

    /* Java bytes are signed: 0x80..0xFF are negative, so they are never in '\t'..'\r'. */
    private static boolean isSpace(byte c) {
        return c == ' ' || (c >= '\t' && c <= '\r'); /* space, \t \n \v \f \r */
    }

    static long run(byte[] data) {
        long words = 0;
        boolean inWord = false;
        for (byte c : data) {
            if (isSpace(c)) {
                inWord = false;
            } else if (!inWord) {
                inWord = true;
                words++;
            }
        }
        return words;
    }

    static long digest() {
        return 0;
    }
}
