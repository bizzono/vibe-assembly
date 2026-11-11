# Shootout protocol

Every entry is a command-line program that times one kernel on one input file and
prints one line. All languages follow exactly the same steps, so the only thing that
differs between two entries is the language.

## Invocation

```
prog <input-file> <min_ms>
```

## What the program does

1. Read the whole input file into memory as bytes. (Not timed.)
2. If `min_ms` is `0` ("cold" mode): call `run(data)` exactly once, timing it, then print
   the result line with `0` as the digest (do **not** call `digest()`) and `calls = 1`.
   Cold mode exists so the runner can time one whole process from the outside.
3. Otherwise call `run(data)` once without timing it and remember the result (warm-up).
4. Call `run(data)` repeatedly. Time each call on its own with the language's
   monotonic nanosecond clock. After each call check the result equals the warm-up
   result (exit with an error if not). Stop when **at least 3 calls** have been made
   **and** (the sum of the timed durations is at least `min_ms` milliseconds **or**
   1,000,000 calls have been made).
5. Call `digest()` once. (Not timed.)
6. Print exactly one line to stdout and exit with status 0:

   ```
   RESULT <result> <digest> <best_ns> <calls>
   ```

   `result` is what `run` returned, `digest` what `digest` returned (both unsigned 64-bit,
   decimal), `best_ns` the **minimum** duration of a single timed call in nanoseconds
   (integer), `calls` the number of timed calls.

## The kernel

Each kernel is one source file per language defining two functions (names adapted to
the language's conventions):

- `run(data: bytes) -> u64` -- the timed work.
- `digest() -> u64` -- an untimed check of any output `run` produced. Kernels that only
  return a number return `0`. Kernels that fill an output buffer return the 64-bit
  FNV-1a hash of the bytes written by the last `run` (offset basis
  `0xcbf29ce484222325`, prime `0x100000001b3`).

| kernel          | input file                                   | `run` returns                 | `digest` |
|-----------------|----------------------------------------------|-------------------------------|----------|
| `wordcount`     | 8 MiB of text                                | number of words               | 0        |
| `utf8_validate` | 8 MiB of valid mixed UTF-8                   | 1 if well-formed, else 0      | 0        |
| `crc32`         | 8 MiB of random bytes                        | CRC-32 (zlib/PNG polynomial)  | 0        |
| `base64_encode` | 6 MiB of random bytes                        | bytes written (8 MiB)         | FNV-1a of the Base64 text |
| `mandelbrot`    | 12 bytes: `width`, `height`, `max_iter` as little-endian `u32` | sum of iteration counts | 0 |
| `nqueens`       | 4 bytes: `n` as little-endian `u32`          | number of solutions           | 0        |

The exact contract of each kernel is `tasks/<kernel>/SPEC.md`; the reference
implementation is `tasks/<kernel>/ref.c`.

## Rules for implementations

These exist so the comparison is about the language, not about who knew which library.

1. **Same algorithm as the reference.** Port `tasks/<kernel>/ref.c` faithfully and
   idiomatically: same loop structure, same table-driven CRC, same recursive bitmask
   search, same operation order for the floating-point kernel. No smarter algorithm, no
   symmetry tricks, no precomputed answers.
2. **The language does the work.** The kernel may not call a library routine that does
   the kernel's job (no `zlib.crc32`, no `base64` module, no `len(data.split())`, no
   `String(validatingUTF8:)`, no `isUtf8`), no FFI, no inline assembly, no SIMD
   intrinsics, no threads. Ordinary core-language features and containers are fine.
3. **Idiomatic and reasonably fast.** Write it the way a competent user of the language
   writes a hot loop: typed arrays in JavaScript, `bytes`/local variables in Python,
   slices in Go and Rust, unsafe buffer pointers in Swift where a performance-minded
   Swift programmer would use them. Use the optimized build of the toolchain. Do not
   de-optimize, and do not hand-vectorize.
4. **Bit-exact results.** Every entry must print the same `result` and `digest` as the C
   reference, or it is disqualified. For `mandelbrot` that means IEEE-754 doubles with
   **no fused multiply-add**: each `*`, `+`, `-` is its own correctly-rounded operation
   (in Go, wrap products in `float64(...)` to stop the compiler fusing them).
5. Output buffers (Base64) are allocated once, on the first call to `run`, and reused.
   Allocation is not what is being measured.
6. The warm-up call and "minimum of many calls" are there for the JIT-compiled
   languages: their steady-state speed is what is reported.

The assembly entry follows the same protocol with a `main` that is itself written in
assembly (`langs/asm/main.s`); the kernels it calls are the harness-verified files in
`solutions/`.
