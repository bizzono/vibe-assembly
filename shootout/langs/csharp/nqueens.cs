// nqueens kernel (C#): a port of tasks/nqueens/ref.c, the textbook bitmask backtracking search.
using System.Buffers.Binary;

internal static class Kernel
{
    private static ulong Place(uint all, uint cols, uint diagL, uint diagR)
    {
        if (cols == all) return 1;
        ulong count = 0;
        uint free = all & ~(cols | diagL | diagR);
        while (free != 0)
        {
            uint bit = free & (0 - free); // lowest free square in this row
            free ^= bit;
            count += Place(all, cols | bit, (diagL | bit) << 1, (diagR | bit) >> 1);
        }
        return count;
    }

    private static ulong NQueens(ulong n)
    {
        if (n > 31) return 0;
        uint all = (uint)((1UL << (int)n) - 1);
        return Place(all, 0, 0, 0);
    }

    public static ulong Run(ReadOnlySpan<byte> data)
    {
        uint n = 0;
        if (data.Length >= 4) n = BinaryPrimitives.ReadUInt32LittleEndian(data);
        return NQueens(n);
    }

    public static ulong Digest() => 0;
}
