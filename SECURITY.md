# Security Policy

## Security & Trust Model

`vibe-assembly` is built around a single core assumption: **assembly produced by an LLM agent (or an untrusted contributor) is adversarial or subtly broken until proven otherwise.**

### 1. Candidate Assembly Verification Gates

Before any candidate `.s` file is accepted or benchmarked, the harness enforces five layered defenses:

1. **Static Source & Directive Lint ([`vibeasm/lint.py`](vibeasm/lint.py))**:
   - Rejects system call instructions (`svc`, `hvc`, `smc`, `syscall`, `sysenter`, `int`, `int3`, `ud2`, `hlt`).
   - Rejects system register access (`msr`/`mrs` other than `nzcv`, `rdmsr`, `wrmsr`) and platform-reserved registers (`x18`).
   - Rejects file-inclusion directives (`.include`, `.incbin`) and architecture-escalation directives (`.arch`, `.arch_extension`, `.cpu`).
2. **Object Symbol & Section Hygiene ([`vibeasm/lint.py`](vibeasm/lint.py))**:
   - Verifies that the assembled object exports **only** the target symbol in the `.text` / `__TEXT,__text` section and contains **zero** undefined external symbols (`nm -u`).
   - Rejects any object containing writable data sections (`.data`, `.bss`, `.tdata`, `.tbss`), guaranteeing that accepted kernels are stateless, pure leaf functions that cannot persist state across calls or introduce data races.
3. **Hostile-Caller ABI Trampoline ([`vibeasm/kit/`](vibeasm/kit/))**:
   - Poisons caller-saved general and SIMD/FP registers before every call so uninitialized register reads fail deterministically.
   - Places per-call canary values in all callee-saved registers (`x19`–`x29`, `d8`–`d15` on ARM64; `rbx`, `rbp`, `r12`–`r15` on x86-64) and verifies stack pointer restoration after return.
4. **Hardware Page-Guarded Arenas ([`vibeasm/kit/driver.c`](vibeasm/kit/driver.c))**:
   - Surrounds every input and output buffer with unmapped `PROT_NONE` guard pages (`mmap` + `mprotect`) and tests buffers placed flush against both the leading and trailing guard pages.
   - Marks input buffers read-only (`PROT_READ`) so any attempt to mutate input memory faults immediately with `SIGSEGV`/`SIGBUS`.
5. **Hold-Out Differential Fuzzing ([`vibeasm/loop.py`](vibeasm/loop.py))**:
   - Evaluates candidates on hold-out PRNG seeds distinct from those available during interactive `vibeasm check`, followed by a final full-profile verification pass before installation into [`solutions/`](solutions/).

### 2. Headless Agent Confinement

When running an autonomous agent via `bin/vibeasm run`:
- The child environment sets `VIBEASM_SANDBOX=1` ([`vibeasm/agent.py`](vibeasm/agent.py)), blocking privileged CLI subcommands (`run`, `accept`, `new`, `verify --update`) inside the agent session.
- Headless Claude Code sessions are invoked with `--safe-mode`, `--restricted`, `--no-session-persistence`, `--permission-prompts none`, and an explicit tool allowlist (`Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash(vibeasm *)`).
- A wall-clock watchdog timer terminates the entire process group (`os.killpg`) if an agent round exceeds its timeout.

### 3. Scope Limitations

- **Constant-Time Execution**: The harness verifies functional equivalence, memory safety, and ABI compliance, **not** constant-time execution. Do not use `vibe-assembly` kernels for cryptographic secret processing without an independent side-channel / constant-time analysis.
- **Local Execution During Fuzzing**: Although static lint rejects `svc`/`syscall` mnemonics and external symbol references before execution, candidate machine code is executed inside the local `driver` process during Gate 3–5 testing. If you are feeding untrusted third-party `.s` files from external networks into `vibeasm check`, run the harness inside an unprivileged container or VM.

## Supported Versions

| Version | Supported |
|---|---|
| `0.1.x` (`main`) | Yes |

## Reporting a Vulnerability

If you discover a verification gate bypass (e.g., an assembly file that violates ABI invariants, reads/writes out of bounds, or retains mutable state without being caught by `vibeasm check`) or a sandbox escape in `vibeasm run`:

1. **Please open a GitHub Security Advisory** on [https://github.com/bizzono/vibe-assembly/security/advisories](https://github.com/bizzono/vibe-assembly/security/advisories) (or file an issue with a minimal reproducer `.s` file if non-sensitive).
2. Every confirmed gate bypass will be added as a permanent regression test in [`tests/zoo/`](tests/zoo/).
