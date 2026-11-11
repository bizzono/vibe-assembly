# Notes for agents working on this repository

This repository is a harness that lets an LLM agent write assembly and refuses to
trust the result until it has verified it. Read `README.md` for the idea and
`docs/HOW_IT_WORKS.md` for the design.

## Layout

- `vibeasm/` the harness (Python 3.9+, standard library only). `kit/` is the C test
  driver and the assembly ABI trampoline; `prompts/` is what an agent is told.
- `tasks/<name>/` a contract (`SPEC.md`), an oracle (`ref.c`), input generators
  (`gen.c`) and benchmark cases (`task.json`).
- `solutions/<target>/<name>.s` verified assembly, each with a `.json` provenance record.
- `shootout/` the same kernels in other languages, and the runner that times them.
- `tests/` tests of the harness itself, including `zoo/`: assembly that is wrong in one
  specific way each.
- `video/` the Remotion project that renders the README preview from real results.

## Rules

- **Never edit a file in `solutions/` by hand.** Solutions enter through
  `vibeasm run` or `vibeasm accept`, which verify them and write the provenance record.
- **Never weaken a gate to make something pass.** If a candidate fails, the candidate
  is wrong. If you believe the gate is wrong, add a test in `tests/` that shows it.
- **Never report a number the tools did not print.** Benchmarks are noisy; quote the
  harness's output, and say when a difference is inside the noise.
- Keep the harness dependency-free: Python standard library, a C compiler, `nm`,
  `otool`, `objdump`.
- When you change a gate, add a zoo file that the old gate would have let through.

## Commands

```
bin/vibeasm doctor                    # toolchain check
python3 -m unittest discover -s tests # the harness's own tests (about two minutes)
bin/vibeasm verify                    # re-verify and re-time every installed solution
python3 shootout/shootout.py --quick  # smoke-test every language entry
```

To write assembly with the harness, follow `.claude/skills/vibe-assembly/SKILL.md`.
