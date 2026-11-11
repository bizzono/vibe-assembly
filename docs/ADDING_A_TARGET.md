# Adding a target

Today the harness supports one target, `arm64-darwin` (Apple Silicon Macs), because
that is the machine it was built and verified on. Assembly is only as good as its
verification, and verification means running it, so a target is not "supported" until
someone has run the whole test suite on real hardware for it.

The task format, the driver, the fuzz schedule and the agent loop are target
independent. A new target needs four things.

## 1. An entry in `vibeasm/target.py`

A `Target` names the compiler, the flags for assembling a candidate, the flags for the
compiler baseline, the shared-library extension and the symbol prefix (`_` on Mach-O,
nothing on ELF). Choose the assembler's CPU baseline deliberately: it decides which
machines a verified solution will run on. For `x86_64-linux` that is the difference
between `-march=x86-64-v2` (runs everywhere, no AVX2) and `-march=x86-64-v3`.

## 2. A trampoline: `vibeasm/kit/tramp_<target>.s`

The trampoline calls the candidate the way the most hostile legal caller would. Port
`tramp_arm64_darwin.s`:

- put canaries in every callee-saved register and compare them after the call;
- put garbage in every caller-saved register, the unused argument registers and the
  flags before the call;
- check the stack pointer (and frame pointer, where the ABI has one) afterwards;
- report violations as a bit mask, and extend `abi_reg_name()` in `driver.c`.

For x86-64 System V the callee-saved set is `rbx`, `rbp`, `r12`-`r15`; also check that
the direction flag is clear on return and that the x87/MXCSR control words are intact.

## 3. Crash decoding in `driver.c`

`on_signal()` reads the program counter, stack pointer and general registers out of the
signal context. That structure is different on every OS and ISA; add a branch for
yours. Everything else in the driver is portable C.

## 4. Static inspection in `vibeasm/lint.py`

The lint reads the object file with `nm`, `otool` and `objdump`. For ELF, read
sections with `readelf -S` or `objdump -h` and reject anything writable (`.data`,
`.bss`). Update the forbidden mnemonics for the ISA (`syscall`, `int`, `sysenter`,
`rdmsr`, ... on x86).

## 5. An ABI sheet: `vibeasm/prompts/abi_<target>.md`

This is what the agent is told about the target: registers, calling convention, file
skeleton, how to address constants, which CPU features it may assume, and the traps.
Check every statement against the platform's ABI document, not from memory. An agent
that is told something false will write code that is confidently wrong.

## Then prove it

```
python3 -m unittest discover -s tests
```

The zoo in `tests/zoo/` is written in arm64 assembly; a new target needs its own copies
of those files (each one is a dozen lines with one deliberate bug). The tests that
inject bugs through a wrapper around the compiler's output need the wrapper's few
instructions translated. When the whole suite passes on real hardware, the target is
supported.

Solutions do not carry over between targets, and they are not supposed to. The
contract, the reference and the generators carry over unchanged; the assembly is
written again by the agent and verified again by the harness.
