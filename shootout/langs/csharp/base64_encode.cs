// base64_encode kernel (C#): a port of tasks/base64_encode/ref.c.
internal static class Kernel
{
    private static ReadOnlySpan<byte> Alphabet =>
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"u8;

    private static byte[]? s_out; // allocated on the first call, then reused
    private static int s_outLen;

    private static int Encode(ReadOnlySpan<byte> src, Span<byte> dst)
    {
        ReadOnlySpan<byte> alphabet = Alphabet;
        int len = src.Length;
        int i = 0, o = 0;
        // The reference's loop, with two spellings chosen for the JIT: the bound is written
        // `i <= len - 3` (not `i + 3 <= len`) so the bounds checks on src are proven away, and
        // the four stores use `o + k` with one `o += 4` instead of four `o++`, which RyuJIT
        // would otherwise turn into a serial chain of increments.
        for (; i <= len - 3; i += 3, o += 4)
        {
            uint v = (uint)src[i] << 16 | (uint)src[i + 1] << 8 | src[i + 2];
            dst[o] = alphabet[(int)(v >> 18)];
            dst[o + 1] = alphabet[(int)((v >> 12) & 63)];
            dst[o + 2] = alphabet[(int)((v >> 6) & 63)];
            dst[o + 3] = alphabet[(int)(v & 63)];
        }
        if (len - i == 1)
        {
            uint v = (uint)src[i] << 16;
            dst[o++] = alphabet[(int)(v >> 18)];
            dst[o++] = alphabet[(int)((v >> 12) & 63)];
            dst[o++] = (byte)'=';
            dst[o++] = (byte)'=';
        }
        else if (len - i == 2)
        {
            uint v = (uint)src[i] << 16 | (uint)src[i + 1] << 8;
            dst[o++] = alphabet[(int)(v >> 18)];
            dst[o++] = alphabet[(int)((v >> 12) & 63)];
            dst[o++] = alphabet[(int)((v >> 6) & 63)];
            dst[o++] = (byte)'=';
        }
        return o;
    }

    public static ulong Run(ReadOnlySpan<byte> data)
    {
        s_out ??= new byte[4 * ((data.Length + 2) / 3)];
        s_outLen = Encode(data, s_out);
        return (ulong)s_outLen;
    }

    /// <summary>64-bit FNV-1a of the bytes written by the last Run().</summary>
    public static ulong Digest()
    {
        ulong h = 0xcbf29ce484222325UL;
        foreach (byte b in s_out.AsSpan(0, s_outLen))
        {
            h = (h ^ b) * 0x100000001b3UL;
        }
        return h;
    }
}
