# Contributing to vibe-assembly

Thank you for contributing to `vibe-assembly`! This repository is a verification and benchmarking harness for machine code—precision, reproducibility, and gate integrity come first.

## Golden Rules

1. **Never edit a file in [`solutions/`](solutions/) by hand.**
   Every `.s` file and `.json` provenance record in `solutions/` must be installed through `bin/vibeasm run` or `bin/vibeasm accept`, which run the full verification profile with fresh hold-out seeds and record the benchmark timings.
2. **Never weaken a verification gate to make a candidate pass.**
   If a candidate fails a gate, the candidate is wrong. If you believe a gate has a false positive, add a minimal reproduction test in [`tests/test_harness.py`](tests/test_harness.py) that demonstrates it.
3. **Every gate change requires a [`tests/zoo/`](tests/zoo/) regression file.**
   When tightening or adding a gate check, add a small `.s` file in `tests/zoo/` that fails that specific check and register it in `EXPECT` in [`tests/test_harness.py`](tests/test_harness.py).
4. **Never report a benchmark number the tools did not print.**
   Always quote the exact output of `bin/vibeasm bench` or `python3 shootout/shootout.py`, and note when differences are within measurement noise (~5%).
5. **Keep the harness zero-dependency.**
   `vibeasm/` uses only the Python 3.9+ standard library and standard system toolchain utilities (`clang`, `nm`, `objdump`, and `otool` on macOS).

## Development Workflow

```sh
# 1. Verify your local toolchain
bin/vibeasm doctor

# 2. Run the full harness unit and zoo test suite
python3 -m unittest discover -s tests -v

# 3. Quick-verify all installed assembly solutions
bin/vibeasm verify --quick

# 4. Build the C/Assembly static & shared libraries and run examples
make all && make examples && make clean
```

## Guides for Common Contributions

- **Adding a new benchmark/assembly task**: Follow [`docs/WRITING_A_TASK.md`](docs/WRITING_A_TASK.md) (`bin/vibeasm new <name>`).
- **Adding a new ISA/OS target**: Follow [`docs/ADDING_A_TARGET.md`](docs/ADDING_A_TARGET.md).
- **Adding or updating a shootout language entry**: Follow [`shootout/PROTOCOL.md`](shootout/PROTOCOL.md) and test with `python3 shootout/shootout.py --quick --no-write`.

## Pull Request Checklist

- [ ] `python3 -m unittest discover -s tests -v` passes with zero errors.
- [ ] `bin/vibeasm verify --quick` passes for all installed solutions.
- [ ] `make all && make examples && make clean` succeeds without warnings.
- [ ] If a verification gate was modified, a corresponding regression test was added to `tests/zoo/`.
