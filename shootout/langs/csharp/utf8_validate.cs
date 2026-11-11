// utf8_validate kernel (C#): a port of tasks/utf8_validate/ref.c, itself a direct
// transcription of Table 3-7 ("Well-Formed UTF-8 Byte Sequences") of the Unicode Standard.
internal static class Kernel
{
    private static bool In(byte c, byte lo, byte hi) => c >= lo && c <= hi;

    public static ulong Run(ReadOnlySpan<byte> s)
    {
        int n = s.Length;
        int i = 0;
        while (i < n)
        {
            byte c = s[i];
            if (c < 0x80)
            {
                i += 1;
            }
            else if (In(c, 0xC2, 0xDF))
            {
                if (n - i < 2 || !In(s[i + 1], 0x80, 0xBF)) return 0;
                i += 2;
            }
            else if (In(c, 0xE0, 0xEF))
            {
                byte lo = c == 0xE0 ? (byte)0xA0 : (byte)0x80; // E0: no overlong encodings
                byte hi = c == 0xED ? (byte)0x9F : (byte)0xBF; // ED: no UTF-16 surrogates
                if (n - i < 3 || !In(s[i + 1], lo, hi) || !In(s[i + 2], 0x80, 0xBF)) return 0;
                i += 3;
            }
            else if (In(c, 0xF0, 0xF4))
            {
                byte lo = c == 0xF0 ? (byte)0x90 : (byte)0x80; // F0: no overlong encodings
                byte hi = c == 0xF4 ? (byte)0x8F : (byte)0xBF; // F4: nothing above U+10FFFF
                if (n - i < 4 || !In(s[i + 1], lo, hi) || !In(s[i + 2], 0x80, 0xBF) || !In(s[i + 3], 0x80, 0xBF))
                {
                    return 0;
                }
                i += 4;
            }
            else
            {
                return 0; // 80..C1 and F5..FF never start a sequence
            }
        }
        return 1;
    }

    public static ulong Digest() => 0;
}
