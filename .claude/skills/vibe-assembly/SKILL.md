---
name: vibe-assembly
description: Write a function directly in assembly instead of a high-level language, verified against a reference and benchmarked against the optimizing compiler, using this repository's `vibeasm` harness. Use when the user asks for assembly, for "the fastest possible" version of a hot function, to beat the compiler, or to add a task or solution to this repository.
---

# Writing assembly with the vibe-assembly harness

You are in the vibe-assembly repository. The harness (`bin/vibeasm`) assembles a
candidate, lints it, fuzzes it differentially against a reference implementation under
guard pages and an ABI-checking trampoline, and times it against `clang -O3`. Your job
is to write the assembly; the harness's job is to not believe you. Never report a
result the harness did not print.

Run `bin/vibeasm doctor` first. If the target is unsupported, say so and stop: assembly
is verified by running it.

## 1. Pin down the task (the part the human reviews)

If the user wants a new function, create a task. A task is a contract plus an oracle:

```
bin/vibeasm new <name> --shape bytes_to_u64      # or bytes_to_bytes, or ints_to_u64 --args a,b
```

Then fill in `tasks/<name>/`:

- `SPEC.md`: the contract in prose. Every edge case stated: empty input, largest
  input, bytes >= 0x80, overflow, what exactly is returned.
- `ref.c`: the reference implementation. Plain, boring, obviously correct C. If the
  user's function is in another language, translate it faithfully and show them.
- `gen.c`: input generators. Flavor 0 is the typical input (benchmarks use it). Add
  adversarial flavors: the inputs most likely to break a vectorized implementation
  (all-matches, no-matches, boundary byte values, almost-valid data with one defect).
- `task.json`: benchmark cases (include small sizes) and `goal_speedup`.

Show the user `SPEC.md` and `ref.c` and get their agreement before optimizing: nobody
will read the assembly, so these two files are the review.

Sanity-check the task itself: the compiler's own output must pass.

```
bin/vibeasm baseline <name> > /tmp/compiler.s && bin/vibeasm check <name> /tmp/compiler.s --full
```

## 2. Write the assembly

Either hand the task to a headless agent, which loops until verified:

```
bin/vibeasm run <name> --rounds 3
```

or do it yourself in a work directory:

```
bin/vibeasm work <name>          # prints the directory; cd there
```

In the work directory read `TASK.md` (the brief: rules, tools, judging) and `ABI.md`
(registers, syntax, traps) before writing code, then iterate:

```
vibeasm check                    # assemble + lint + thousands of differential tests (~1 s)
vibeasm bench a.s b.s            # time variants side by side against the compiler
vibeasm call --text 'input'      # one input through your code and the reference
vibeasm call --gen 16177 --flavor 4
vibeasm disasm --lines
```

Get a simple correct version passing first. Then optimize by measuring: one idea per
file, compare with `bench`, keep what the numbers favour. Keep notes in `NOTES.md`.

## 3. Have it accepted

```
bin/vibeasm accept <name> <path/to/solution.s> --by "claude-code interactive" --model <model>
```

This runs the long verification with fresh seeds, benchmarks, and installs the file
in `solutions/<target>/` with a provenance record. If it refuses, fix the bug it
reports; do not use `--force` to get around a failure.

## 4. Report honestly

Tell the user the measured speed-up per case from the harness's table, the number of
test cases it passed, and the limits: verified by differential fuzzing (strong
evidence, not proof), for this target only. If the assembly is not faster than the
compiler, say that plainly: it is a real and common result for code the compiler
already handles well.

## Rules for solutions (the lint enforces them)

One exported symbol; no external references; no writable data; no reads or writes
outside the buffers (not even inside a vector load); callee-saved registers, `sp` and
`x29` preserved; no `x18`, `svc`, system registers, or `.arch`/`.cpu` directives.
