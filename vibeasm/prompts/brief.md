# Write the fastest correct assembly for `{symbol}`

You are writing **{target} assembly by hand**. No compiler stands between you and the
machine: the instructions you write are the instructions that run. A harness will
assemble your file, compare it with a reference implementation on thousands of inputs,
and time it against what `{baseline_desc}` makes of the reference C.

Your goal, in this order: **correct, then as fast as you can make it.**

## The contract

```c
{signature}
```

{spec}

The reference implementation is in `ref.c`. It *defines* the behaviour: if the prose
above and `ref.c` ever disagree, `ref.c` wins (mention it in your final message).

## What you deliver

One file, `solution.s`, in the current directory, defining `{asm_symbol}`.
{deliver_note}

## Hard rules (checked mechanically; a violation is a rejection)

1. **Self-contained.** Export exactly one symbol, `{asm_symbol}`. No calls or
   references to anything outside the file: no libc, no reference implementation.
2. **Stateless.** No writable data (`.data`, `.bss`). Read-only constants go in
   `.section __TEXT,__const`; scratch space goes on the stack.
3. **Stay inside the buffers.**{buffer_rule}
4. **Keep the calling convention.** `x19`-`x28`, `x29`, `sp` and `d8`-`d15` must hold the
   same values on return as on entry. The harness calls you through a trampoline that
   fills *every other* register (and the flags) with garbage first, so nothing is zero
   by luck, and checks the callee-saved ones afterwards.
5. **No `x18`, no system calls (`svc`), no system registers, no `.arch`/`.cpu`
   directives.** CPU features you may assume: {features}.
{extra_rules}
Details of the registers, the assembler syntax and the usual traps are in `ABI.md`.
Read it before writing code.

## Your tools

{tools}

## How you are judged

When you finish, the harness runs a **longer check with seeds you have not seen**, then
the benchmark below. Your score is the geometric mean of the speed-ups over all cases,
so every case counts{small_note}.

{bench_cases}

Baseline to beat: `{baseline_desc}` compiling `ref.c`. Its assembly is in
`baseline.s`. Goal for this task: **{goal}x or better**.{best_note}

## How to work

1. Read `ref.c`, then `baseline.s`: see what the compiler did and where it left
   performance behind (a serial dependency chain? no vectorization? a table lookup where
   an instruction exists?).
2. **Get something simple and correct passing first.** A plain scalar loop is fine. Do
   not start with the clever version: you need a known-good file to fall back on and to
   measure against.
3. **Then optimize by measuring, not by intuition.** Put each idea in its own file
   (`v2_neon.s`, `v3_unrolled.s`, ...) and compare them directly:
   `vibeasm bench v2_neon.s v3_unrolled.s`. Keep whatever the numbers favour. Ideas that
   sound fast are often slower; ideas that sound silly sometimes win.
4. Things worth trying, depending on the task:
   - process 16 bytes (or several vectors) per iteration with NEON; unroll so several
     vectors are in flight at once;
   - break one long dependency chain into several independent ones (separate
     accumulators, interleaved streams) -- these cores run many chains in parallel;
   - use an instruction that does the job outright (`crc32x`, `pmull`, `cnt`, `tbl`,
     `uaddlv`, `umaxv`, the AES/SHA instructions);
   - replace unpredictable branches with `csel`/`ccmp`/masks, and keep predictable ones;
   - give small inputs their own short path: the benchmark includes tiny inputs, where
     set-up cost dominates;
   - handle the tail without reading past the end (see `ABI.md`).
5. Keep a lab notebook in `NOTES.md`: what you tried, what it measured, what you would
   try next. Later rounds (possibly a different agent) start from those notes.
6. **Before you finish**, `solution.s` must be your fastest version that *passes*:
   run `vibeasm check solution.s --full` and `vibeasm bench solution.s` one last time.
   A fast file that fails the check scores zero; a correct file that is only as fast as
   the compiler still counts.

{feedback}
## When you are done

Reply with a short final message: the approach you ended on, the speed-up you measured,
and what you would try next with more time.
