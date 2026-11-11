/* Shootout driver (Java). See shootout/PROTOCOL.md. */
import java.io.IOException;
import java.lang.invoke.MethodHandles;
import java.nio.file.Files;
import java.nio.file.Path;

public final class Main {
    private Main() {}

    public static void main(String[] args) throws IllegalAccessException {
        if (args.length != 2) {
            System.err.println("usage: Main <input-file> <min_ms>");
            System.exit(2);
        }
        byte[] data;
        try {
            data = Files.readAllBytes(Path.of(args[0]));
        } catch (IOException e) {
            System.err.println(args[0] + ": " + e);
            System.exit(2);
            return;
        }
        long minNs = Long.parseUnsignedLong(args[1]) * 1_000_000L;

        // Java initialises a class on first use, which would otherwise be inside the first
        // call of run(): build the kernel's static tables before anything is timed.
        MethodHandles.lookup().ensureInitialized(Kernel.class);

        if (minNs == 0) { // cold mode: one call, no digest
            long t0 = System.nanoTime();
            long result = Kernel.run(data);
            long dt = System.nanoTime() - t0;
            System.out.println("RESULT " + Long.toUnsignedString(result) + " 0 " + dt + " 1");
            return;
        }

        long warm = Kernel.run(data);
        long result = warm, best = Long.MAX_VALUE, total = 0, calls = 0;
        while (calls < 3 || (total < minNs && calls < 1_000_000)) {
            long t0 = System.nanoTime();
            result = Kernel.run(data);
            long dt = System.nanoTime() - t0;
            if (result != warm) {
                System.err.println("result changed between calls");
                System.exit(3);
            }
            if (dt < best) best = dt;
            total += dt;
            calls++;
        }
        System.out.println("RESULT " + Long.toUnsignedString(result) + " " + Long.toUnsignedString(Kernel.digest())
                + " " + best + " " + calls);
    }
}
