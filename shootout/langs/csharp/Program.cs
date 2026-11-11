// Shootout driver (C#). See shootout/PROTOCOL.md.
using System.Diagnostics;
using System.Globalization;
using System.Runtime.CompilerServices;

internal static class Program
{
    /// <summary>Stopwatch ticks to nanoseconds (on macOS and Linux a tick already is 1 ns).</summary>
    private static ulong ToNs(long ticks) =>
        (ulong)((UInt128)(ulong)ticks * 1_000_000_000UL / (ulong)Stopwatch.Frequency);

    private static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine("usage: shootout <input-file> <min_ms>");
            return 2;
        }

        byte[] data;
        try
        {
            data = File.ReadAllBytes(args[0]);
        }
        catch (IOException e)
        {
            Console.Error.WriteLine($"{args[0]}: {e.Message}");
            return 2;
        }

        ulong minNs = ulong.Parse(args[1], CultureInfo.InvariantCulture) * 1_000_000UL;

        // .NET runs a type's static initialisers on first use, which would otherwise be inside
        // the first call of Run(): build the kernel's static tables before anything is timed.
        RuntimeHelpers.RunClassConstructor(typeof(Kernel).TypeHandle);

        if (minNs == 0)
        {
            // Cold mode: one call, no digest.
            long t0 = Stopwatch.GetTimestamp();
            ulong once = Kernel.Run(data);
            ulong dt = ToNs(Stopwatch.GetTimestamp() - t0);
            Console.WriteLine($"RESULT {once} 0 {dt} 1");
            return 0;
        }

        ulong warm = Kernel.Run(data);
        ulong result = warm, best = ulong.MaxValue, total = 0, calls = 0;
        while (calls < 3 || (total < minNs && calls < 1_000_000))
        {
            long t0 = Stopwatch.GetTimestamp();
            result = Kernel.Run(data);
            ulong dt = ToNs(Stopwatch.GetTimestamp() - t0);
            if (result != warm)
            {
                Console.Error.WriteLine("result changed between calls");
                return 3;
            }
            if (dt < best) best = dt;
            total += dt;
            calls++;
        }

        Console.WriteLine($"RESULT {result} {Kernel.Digest()} {best} {calls}");
        return 0;
    }
}
