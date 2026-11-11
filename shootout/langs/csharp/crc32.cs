// crc32 kernel (C#): a port of tasks/crc32/ref.c, the textbook table-driven CRC-32
// (one table lookup per input byte). The table is built once, by the static initialiser.
internal static class Kernel
{
    private static readonly uint[] s_table = MakeTable();

    private static uint[] MakeTable()
    {
        var table = new uint[256];
        for (uint n = 0; n < 256; n++)
        {
            uint c = n;
            for (int k = 0; k < 8; k++)
            {
                c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
            }
            table[n] = c;
        }
        return table;
    }

    public static ulong Run(ReadOnlySpan<byte> data)
    {
        uint[] table = s_table;
        uint crc = 0xFFFFFFFFu;
        foreach (byte b in data)
        {
            crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8);
        }
        return crc ^ 0xFFFFFFFFu;
    }

    public static ulong Digest() => 0;
}
