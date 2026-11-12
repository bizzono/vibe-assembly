# Shootout results

Apple M4 Pro, macOS 26.7.3. 2026-11-11.
Time for one call of the kernel (minimum over many calls, after warm-up); lower is better. The multiplier is relative to the assembly entry.

| language | Word count | UTF-8 validation | CRC-32 | Base64 encode | Mandelbrot | N-queens | geomean vs asm |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Assembly** | 120 us | 366 us | 76 us | 257 us | 2.17 ms | 2.26 ms | 1.0x |
| **C** | 1.61 ms (13.4x) | 15.18 ms (41.4x) | 15.50 ms (204.6x) | 1.50 ms (5.8x) | 18.98 ms (8.8x) | 3.64 ms (1.6x) | 14.5x |
| **C++** | 1.59 ms (13.2x) | 14.48 ms (39.5x) | 15.76 ms (207.9x) | 1.50 ms (5.8x) | 18.88 ms (8.7x) | 3.63 ms (1.6x) | 14.4x |
| **Rust** | 1.56 ms (13.0x) | 14.55 ms (39.7x) | 15.77 ms (208.1x) | 1.46 ms (5.7x) | 18.84 ms (8.7x) | 3.53 ms (1.6x) | 14.2x |
| **Zig** | 2.62 ms (21.8x) | 15.31 ms (41.8x) | 15.72 ms (207.4x) | 1.51 ms (5.9x) | 18.41 ms (8.5x) | 3.62 ms (1.6x) | 15.7x |
| **Go** | 9.25 ms (77.0x) | 15.40 ms (42.0x) | 16.85 ms (222.4x) | 1.57 ms (6.1x) | 18.97 ms (8.8x) | 4.01 ms (1.8x) | 20.2x |
| **Swift** | 9.83 ms (81.8x) | 15.44 ms (42.1x) | 17.83 ms (235.2x) | 1.50 ms (5.9x) | 19.23 ms (8.9x) | 3.59 ms (1.6x) | 20.2x |
| **Java** | 9.12 ms (76.0x) | 17.07 ms (46.6x) | 17.93 ms (236.6x) | 2.08 ms (8.1x) | 17.81 ms (8.2x) | 3.60 ms (1.6x) | 21.1x |
| **C#** | 8.62 ms (71.7x) | 15.37 ms (41.9x) | 16.99 ms (224.2x) | 2.19 ms (8.5x) | 19.36 ms (8.9x) | 3.50 ms (1.5x) | 20.7x |
| **JavaScript** | 11.04 ms (92.0x) | 17.70 ms (48.3x) | 14.85 ms (195.9x) | 3.85 ms (15.0x) | 19.30 ms (8.9x) | 6.41 ms (2.8x) | 26.3x |
| **Python** | 137 ms (1137.3x) | 139 ms (380.4x) | 451 ms (5950.3x) | 389 ms (1515.0x) | 469 ms (216.6x) | 105 ms (46.3x) | 582.6x |
| **Ruby** | 133 ms (1109.3x) | 342 ms (932.2x) | 135 ms (1782.7x) | 370 ms (1440.7x) | 856 ms (395.4x) | 10.77 ms (4.8x) | 413.6x |

## Cold runs

Wall time of one whole process that runs the kernel once: start-up, reading the input, one call, exit.

| language | Word count | UTF-8 validation | CRC-32 | Base64 encode | Mandelbrot | N-queens |
|---|---:|---:|---:|---:|---:|---:|
| **Assembly** | 3.2 ms | 3.5 ms | 3.8 ms | 3.9 ms | 6.4 ms | 4.9 ms |
| **C** | 4.9 ms | 19.5 ms | 19.6 ms | 5.1 ms | 21.7 ms | 6.5 ms |
| **C++** | 5.0 ms | 18.6 ms | 19.9 ms | 5.3 ms | 21.5 ms | 6.6 ms |
| **Rust** | 4.7 ms | 18.8 ms | 20.0 ms | 5.5 ms | 21.7 ms | 6.5 ms |
| **Zig** | 6.0 ms | 19.9 ms | 20.3 ms | 5.7 ms | 22.5 ms | 6.8 ms |
| **Go** | 13.8 ms | 19.9 ms | 21.7 ms | 6.8 ms | 24.0 ms | 7.5 ms |
| **Swift** | 12.6 ms | 20.4 ms | 22.6 ms | 6.0 ms | 23.0 ms | 7.0 ms |
| **Java** | 42.1 ms | 49.8 ms | 49.7 ms | 37.2 ms | 53.0 ms | 33.7 ms |
| **C#** | 37.0 ms | 41.2 ms | 44.6 ms | 32.9 ms | 45.6 ms | 34.3 ms |
| **JavaScript** | 62.6 ms | 69.8 ms | 66.2 ms | 52.9 ms | 72.7 ms | 54.9 ms |
| **Python** | 152.4 ms | 158.6 ms | 464.7 ms | 405.6 ms | 481.6 ms | 118.5 ms |
| **Ruby** | 164.1 ms | 371.9 ms | 167.0 ms | 403.2 ms | 889.8 ms | 41.5 ms |

## Inputs and toolchains

- **Word count**: 8 MiB of text.
- **UTF-8 validation**: 8 MiB of mixed-script UTF-8.
- **CRC-32**: 8 MiB of random bytes.
- **Base64 encode**: 6 MiB of random bytes.
- **Mandelbrot**: 512 x 512 pixels, 200 iterations.
- **N-queens**: 12 x 12 board.

- **Assembly**: vibe-assembly solutions (arm64-darwin) (written by the agent harness; no compiler)
- **C**: Apple clang version 21.0.0 (clang-2100.1.1.101) (clang -O3 -mcpu=native)
- **C++**: Apple clang version 21.0.0 (clang-2100.1.1.101) (clang++ -O3 -mcpu=native)
- **Rust**: rustc 1.99.1 (58cf8f9c3 2026-10-13) (rustc -C opt-level=3 -C target-cpu=native)
- **Zig**: zig 0.17.1 (ReleaseFast, -mcpu=native)
- **Go**: go version go1.26.4 darwin/arm64 (go build)
- **Swift**: Apple Swift version 6.3.2 (swiftlang-6.3.2.1.108 clang-2100.1.1.101) (swiftc -O)
- **Java**: openjdk 25.0.5 2026-10-20 LTS (HotSpot JIT, after warm-up)
- **C#**: .NET 10.0.403 (.NET JIT, after warm-up)
- **JavaScript**: node v26.12.0 (Node.js (V8 JIT), after warm-up)
- **Python**: Python 3.15.2 (CPython)
- **Ruby**: ruby 4.0.9 (2026-10-23 revision 3e93b23afc) +PRISM [arm64-darwin25] +YJIT (CRuby, YJIT on when the build has it)

Every entry printed the same result as the C reference for every kernel, or it is marked `wrong`.
Rules and method: [PROTOCOL.md](../PROTOCOL.md).

## Token cost & source footprint across all 12 languages

Measured by `python3 shootout/tokens.py` across all 72 implementation files (`solutions/arm64-darwin/*.s`, `tasks/*/ref.c`, and `shootout/langs/*`):

| language | LOC (6 kernels) | bytes | code tokens | 1-shot API ($3/$15 per 1M) | full verified agent loop | warm batch (all 6 kernels) | geomean vs asm |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Assembly** | 1,223 | 36,585 B | 10,740 | $0.172 | $14.52 | 5.2 ms | 1.0x |
| **Rust** | 252 | 8,541 B | 2,528 | $0.049 | — | 55.7 ms | 14.2x |
| **C++** | 241 | 9,620 B | 2,955 | $0.055 | — | 55.8 ms | 14.4x |
| **C** | 182 | 8,725 B | 2,350 | $0.046 | — | 56.4 ms | 14.5x |
| **Zig** | 214 | 7,246 B | 2,312 | $0.045 | — | 57.2 ms | 15.7x |
| **Swift** | 253 | 11,425 B | 3,034 | $0.056 | — | 67.4 ms | 20.2x |
| **Go** | 233 | 6,216 B | 2,070 | $0.042 | — | 66.1 ms | 20.2x |
| **C#** | 240 | 8,305 B | 2,183 | $0.044 | — | 66.0 ms | 20.7x |
| **Java** | 215 | 8,067 B | 2,292 | $0.045 | — | 67.6 ms | 21.1x |
| **JavaScript** | 214 | 6,811 B | 2,242 | $0.044 | — | 73.2 ms | 26.3x |
| **Ruby** | 221 | 6,329 B | 1,716 | $0.037 | — | 1,846.8 ms | 413.6x |
| **Python** | 173 | 6,292 B | 1,716 | $0.037 | — | 1,689.5 ms | 582.6x |
