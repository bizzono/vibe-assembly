# Changelog

All notable changes to `vibe-assembly` are documented in this file.

## [0.1.0] - 2026-11-11

### Added
- **Verification & Benchmarking Harness (`vibeasm/`)**:
  - Five-gate verification pipeline: static source lint (`vibeasm/lint.py`), object symbol & section hygiene (`nm` / `otool` / `objdump`), hostile-caller ABI check trampoline (`tramp_arm64_darwin.s`, `tramp_arm64_linux.s`, `tramp_x86_64_linux.s`), `PROT_NONE` page-guarded arenas (`driver.c`), and differential fuzzing with hold-out seeds (`vibeasm/gates.py`, `vibeasm/loop.py`).
  - CLI commands: `doctor`, `list`, `show`, `check`, `bench`, `call`, `disasm`, `baseline`, `cpu`, `run`, `brief`, `work`, `accept`, `verify`, and `new`.
  - Multi-target support: `arm64-darwin`, `arm64-linux`, and `x86_64-linux`.
- **Six Benchmark Tasks (`tasks/`) & Verified `arm64-darwin` Solutions (`solutions/arm64-darwin/`)**:
  - `crc32` (**88.06x** vs `clang -O3 -mcpu=native`, 194,820 hold-out test cases).
  - `wordcount` (**20.55x** vs `clang -O3 -mcpu=native`, 266,383 hold-out test cases).
  - `utf8_validate` (**11.77x** vs `clang -O3 -mcpu=native`, 302,144 hold-out test cases).
  - `mandelbrot` (**6.71x** vs `clang -O3 -mcpu=native`, 6,000 hold-out test cases).
  - `base64_encode` (**4.79x** vs `clang -O3 -mcpu=native`, 194,840 hold-out test cases).
  - `nqueens` (**2.12x** vs `clang -O3 -mcpu=native`, 2,400 hold-out test cases).
- **12-Language Benchmark Shootout (`shootout/`)**:
  - Implementations across Assembly, C, C++, Rust, Zig, Go, Swift, Java, C#, JavaScript (Node.js), Python, and Ruby (+YJIT) with automated runner (`shootout/shootout.py`) and SVG chart generator (`shootout/chart.py`).
- **SDK, Build System & Examples (`include/`, `examples/`, `Makefile`, `CMakeLists.txt`)**:
  - Public C/C++ header (`include/vibeasm.h`), `Makefile`, and `CMakeLists.txt` building `libvibeasm.a` and shared libraries (`libvibeasm.dylib` / `libvibeasm.so`).
  - Standalone 100% ARM64 assembly Mandelbrot visual renderer (`examples/standalone_mandelbrot.s`) and C integration demo (`examples/fast_cli.c`).
- **Test Suite (`tests/`)**:
  - 28 unit and end-to-end harness tests plus 20 targeted assembly bug-class regression files in `tests/zoo/wordcount/`.
