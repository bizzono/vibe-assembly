# How it works

The harness has one idea: **an agent's claim about its own assembly is worth nothing;
a file that survives the gates is worth something.** Everything below follows from that.

```
            SPEC.md + ref.c + gen.c                      (what a human reviews)
                      |
                      v
   +-----------> brief the agent ------------------+
   |                  |                            |
   |                  v                            |   the agent's own loop:
   |      agent works in a sandboxed directory     |   vibeasm check / bench / call
   |                  |                            |
   |                  v                            |
   |            solution.s  <----------------------+
   |                  |
   |                  v
   |   assemble -> lint -> differential fuzz -> hold-out seeds -> stopwatch
   |                  |
   |      rejected ---+--- verified, fastest so far? keep it
   |          |
   +----------+   (the rejection report is the next round's brief)
                      |
                      v
        final verification with new seeds -> solutions/<target>/<task>.s + provenance
```

## A task

A task is a contract and an oracle, in four small files under `tasks/<name>/`:

| file | what it is |
|---|---|
| `SPEC.md` | The contract, in prose, with every edge case stated. |
| `ref.c` | The reference implementation: plain C, written to be obviously right. Every candidate is compared with it, and compiling it with `clang -O3 -mcpu=native` gives the baseline a solution has to beat. |
| `gen.c` | Input generators. Several "flavors": one typical, the rest adversarial. |
| `task.json` | The function's shape, the benchmark cases, the speed-up to aim for. |

`SPEC.md` and `ref.c` are the source code of the project in the sense that matters:
they are what a person reads, argues about and signs off on. The assembly is a build
artifact that happens to be produced by a model instead of a compiler.

Three function shapes are supported, which covers most hot kernels:

```c
uint64_t f(const uint8_t *buf, size_t len);                  // bytes_to_u64
size_t   f(const uint8_t *src, size_t len, uint8_t *dst);    // bytes_to_bytes
uint64_t f(uint64_t a, uint64_t b, uint64_t c, uint64_t d);  // ints_to_u64 (1 to 4 used)
```

## The gates

A candidate goes through these in order. The first failure stops it and produces a
report written for an agent to act on.

### 1. Assemble

`clang -c -arch arm64 -mcpu=apple-m1 solution.s`. The `-mcpu` matters: the assembler
then refuses instructions that the oldest supported CPU does not have, so a verified
solution runs on every Apple Silicon Mac, not only on the machine that produced it.

### 2. Lint

Static rules, checked on the object file and its disassembly
([`vibeasm/lint.py`](../vibeasm/lint.py)). A solution must be a pure, self-contained
leaf of machine code:

- **One exported symbol**, the task's function.
- **No undefined symbols**: no libc, and no calling the reference implementation.
- **No writable sections.** A solution cannot keep state between calls. That makes it
  thread-safe, and it makes "remember the benchmark's answer" structurally impossible.
- **No `svc`, no system registers**, no `x18` (Apple platforms reserve it).
- **No `.arch` / `.cpu` / `.arch_extension` / `.include` / `.incbin`** in the source.
- **Task-specific forbidden constants**, where a task's answers could be looked up
  instead of computed (`nqueens` forbids the known solution counts).

### 3. Differential fuzzing, under guard pages, through a trampoline

The driver ([`vibeasm/kit/driver.c`](../vibeasm/kit/driver.c)) loads the candidate and
the reference as shared libraries and compares them on generated inputs. Three things
make this much stronger than "run some random tests":

**Guard pages.** Every buffer is placed flush against an unmapped page: at the end of
the buffer (so any over-read or over-write faults), then at the start (so any
under-run faults), then at a random offset (for alignment variety). A 16-byte vector
load that touches one byte past the end is a crash on the spot, not a silent read of
whatever happened to be there. Inputs are mapped read-only during the call, so writing
to the input is a crash too. For functions with an output buffer, everything around it
is filled with a canary pattern and checked afterwards.

**The trampoline.** Calls go through
[`tramp_arm64_darwin.s`](../vibeasm/kit/tramp_arm64_darwin.s), which behaves like the
most hostile caller the ABI allows. Before the call it loads known canaries into every
callee-saved register (`x19`-`x28`, `d8`-`d15`) and garbage into everything else: the
scratch registers, the unused argument registers, all the caller-saved vector registers
and the condition flags. After the call it compares the callee-saved registers, `sp`
and `x29`. Code that "works" because a scratch register happened to be zero, or that
forgets to restore `x19`, fails here on its first call.

**The schedule.** For byte-buffer tasks, per seed:

| phase | what | why |
|---|---|---|
| A | every length from 0 to 160, every flavor, guard at the end and at the start | small sizes are where tail handling goes wrong |
| B | **every length** up to 4,300 (quick) or 17,000 (full), every flavor; plus windows around 8160, 16320, ... 130560 | see below |
| C | thousands of random lengths, flavors, placements and alignments | everything else |
| D | multi-megabyte inputs; lengths around 1 MiB | long loops, 16-bit lane counters |

Phase B exists because of what happened on this project's first live run. The agent
wrote a NEON word counter that kept per-lane byte counters and flushed them every 252
iterations of its 64-byte loop. When the loop ended exactly on a flush boundary, the
tail added four more counts to the same lane, and 252 + 4 wraps a byte. The result was
wrong only when the input was dense with words *and* its length was 16177..16191 modulo
16128. It passed 34,668 random tests and failed the 34,669th-or-so. Random lengths
almost never land in a window like that. Every length in a row always does, so now
every length is tested. That file is kept as a regression test:
[`tests/zoo/wordcount/bad_real_lane_overflow.s`](../tests/zoo/wordcount/bad_real_lane_overflow.s).

A full run on `wordcount` is 133,188 cases in about seven seconds.

**Crash reports.** When a candidate faults, the driver's signal handler (running on its
own stack) records the faulting address, the program counter and every register. The
harness maps the program counter back to a line of the agent's source, labels the fault
relative to the buffers, and hides registers the candidate never wrote:

```
FAIL  your code crashed with SIGBUS on test case #14 (access 1 byte(s) PAST THE END of the input buffer (len=1): over-read)
  input:  case #14  len=1  flavor=prose  placement=end (buffer flush against a guard page)
  where:  bad_overread.s:7   (wordcount+0x4)
          0:  cbz x1, 0x8 <ltmp0+0x8>                      ; line 6
    =>    4:  ldr x9, [x0]                                 ; line 7  <-- here
  registers at the fault (23 others still hold the caller's garbage, i.e. your code never wrote them):
    x0     = 0x0000000104b07fff  in+0
    x1     = 0x0000000000000001
  reproduce:           vibeasm call <file.s> --input .vibeasm-fail/input.bin
```

### 4. Hold-out seeds

The agent can run the check as often as it likes, with seed 1. When it hands a file
back, the harness verifies it again with the full profile and **two fresh random
seeds**, and again with two more before installing. Passing the tests you were shown
is not the same as being right, and this is where the difference shows up.

If a file that verified once fails the final verification, it is never installed. The
failure goes back to the agent as the next round's brief.

### 5. The stopwatch

Candidates and the compiler baseline are loaded into one process and timed in
interleaved order, so drift, thermal state and background load hit all of them alike.

- The reported time is the **minimum** over 41 to 101 samples. Noise on a busy machine
  only ever adds time, so the minimum is the best estimate of what the code costs.
- Each sample repeats the call enough times to last about 0.4 ms, far above the
  clock's 42 ns granularity.
- **Every timed call's result is checked against the reference.** A candidate cannot
  be fast by being wrong, and it cannot special-case the benchmark input: it has no
  writable memory to remember anything in, and two different inputs alternate.
- The score is the geometric mean of the speed-ups over all benchmark cases, small
  sizes included, so a solution cannot win by being good at megabytes and bad at
  sixteen bytes.

A new file replaces the current best only if it scores at least 2% higher; anything
closer than that is timing noise.

Tasks can also list **rivals**: expert implementations, such as the system zlib, that
`vibeasm bench --rivals` times next to the solution. They are never used as the oracle.

## The agent's sandbox

With the default backend the agent is Claude Code running headless
([`vibeasm/agent.py`](../vibeasm/agent.py)), started with:

- file tools confined to the work directory, and no user configuration loaded;
- a shell that will run `vibeasm` and read-only commands inside the work directory,
  and nothing else (no `python`, no `curl`, no reading the rest of your disk);
- no way to answer a permission prompt, so anything not pre-approved is denied.

Inside an agent session the `vibeasm` command itself is cut down to `check`, `bench`,
`call`, `disasm`, `baseline`, `cpu`, `show` and `list`. The agent cannot install a
solution, start another agent, or touch the tests: the oracle, the generators and the
driver live outside its directory, and the harness re-verifies from its own copies.

**What this does not defend against.** The candidate's machine code runs natively, as
you. The lint rejects system calls and external references, which stops accidents and
lazy cheating, but it is not a security boundary against a model that is actively
trying to escape (for instance by jumping into constant data). If you do not trust the
model, run the harness in a VM or a container.

## Provenance

Every installed solution has a record next to it, `solutions/<target>/<task>.json`:
the SHA-256 of the file, the score and per-case times, how many hold-out test cases it
passed and with which seeds, which agent and model wrote it, in how many rounds, at
what cost, on which machine and compiler. `vibeasm verify` re-checks every installed
solution against its task at any time.

## What "verified" means, and what it does not

Verified means: assembled for the baseline CPU, statically self-contained, identical
to the reference on a few hundred thousand inputs chosen to break it, well-behaved at
the ABI level on every one of those calls, and re-checked on inputs it had not seen.

It does not mean proved. Differential fuzzing is strong evidence, not a proof, and the
remaining risk is the kind this project already met once: an input class the generators
do not reach. The defence is better generators, and every bug found becomes one.

It also says nothing about properties nobody tested: timing side channels (do not use
this for secret-dependent code without a constant-time analysis), behaviour on inputs
outside the contract, or other CPUs. A solution is verified for one target. The
contract and the tests carry over to another target; the assembly has to be written
and verified again there.
