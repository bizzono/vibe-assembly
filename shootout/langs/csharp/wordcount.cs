// wordcount kernel (C#): a port of tasks/wordcount/ref.c.
internal static class Kernel
{
    private static bool IsSpace(byte c) =>
        c == (byte)' ' || (c >= (byte)'\t' && c <= (byte)'\r'); // space, \t \n \v \f \r

    public static ulong Run(ReadOnlySpan<byte> data)
    {
        ulong words = 0;
        bool inWord = false;
        foreach (byte c in data)
        {
            if (IsSpace(c))
            {
                inWord = false;
            }
            else if (!inWord)
            {
                inWord = true;
                words++;
            }
        }
        return words;
    }

    public static ulong Digest() => 0;
}
