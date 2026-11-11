// mandelbrot kernel (C#): a port of tasks/mandelbrot/ref.c. C# doubles are IEEE-754 binary64
// and the JIT does not fuse a multiply and an add (that takes an explicit
// Math.FusedMultiplyAdd), as the contract needs.
using System.Buffers.Binary;

internal static class Kernel
{
    private static ulong Mandelbrot(ulong width, ulong height, ulong maxIter)
    {
        ulong total = 0;
        if (width == 0 || height == 0) return 0;
        double dx = 3.0 / (double)width;
        double dy = 3.0 / (double)height;
        for (ulong py = 0; py < height; py++)
        {
            double ci = -1.5 + (double)py * dy;
            for (ulong px = 0; px < width; px++)
            {
                double cr = -2.0 + (double)px * dx;
                double zr = 0.0, zi = 0.0;
                ulong n = 0;
                while (n < maxIter)
                {
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

    public static ulong Run(ReadOnlySpan<byte> data)
    {
        uint width = 0, height = 0, maxIter = 0;
        if (data.Length >= 12)
        {
            width = BinaryPrimitives.ReadUInt32LittleEndian(data);
            height = BinaryPrimitives.ReadUInt32LittleEndian(data[4..]);
            maxIter = BinaryPrimitives.ReadUInt32LittleEndian(data[8..]);
        }
        return Mandelbrot(width, height, maxIter);
    }

    public static ulong Digest() => 0;
}
