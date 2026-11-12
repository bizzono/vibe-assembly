---
name: vibe-assembly
description: Write a function directly in assembly instead of a high-level language, verified against a reference and benchmarked against the optimizing compiler, using this repository's `vibeasm` harness.
---

# Writing assembly with the vibe-assembly harness (OpenAI Codex / CLI)

1. Run `bin/vibeasm doctor` to check the host target (`arm64-darwin`, `arm64-linux`, or `x86_64-linux`).
2. To create a new task contract and C oracle:
   ```sh
   bin/vibeasm new <name> --shape bytes_to_u64
   ```
   Fill in `tasks/<name>/SPEC.md`, `ref.c`, `gen.c`, and `task.json`.
3. To prepare an interactive work directory with `TASK.md`, `ABI.md`, `ref.c`, `baseline.s`, and `solution.s`:
   ```sh
   bin/vibeasm work <name>
   ```
4. Iterate on `solution.s` using the 5-gate verifier and timer:
   ```sh
   bin/vibeasm check <name> runs/<name>/manual/work/solution.s
   bin/vibeasm bench <name> runs/<name>/manual/work/solution.s
   bin/vibeasm call <name> runs/<name>/manual/work/solution.s --text "test input"
   ```
5. Install into `solutions/<target>/` only through full hold-out verification:
   ```sh
   bin/vibeasm accept <name> runs/<name>/manual/work/solution.s --by "codex"
   ```
