# Writing a task

A task tells the harness what function you want and how to recognise a correct one.
It takes a few minutes, and it is the only part of the process a person has to review.

```
bin/vibeasm new hexdigits --shape bytes_to_u64
```

That creates `tasks/hexdigits/` with four files that already run end to end. Edit them.

## 1. `SPEC.md`: the contract

Say exactly what the function returns. The agent will exploit every ambiguity in the
direction of speed, so close them:

- What happens on empty input? On the largest input?
- Are bytes `>= 0x80` special? Is the input guaranteed to be text, or arbitrary bytes?
- Can a counter overflow? What is returned then?
- For output buffers: exactly how many bytes may be written.

If you find yourself writing "obviously" or "as usual", that is the sentence to replace
with a rule. Rules the benchmark depends on belong here too (see `tasks/nqueens/SPEC.md`,
which forbids symmetry tricks so that every language runs the same search).

## 2. `ref.c`: the oracle

The reference implementation decides what is correct. Write it for clarity, not speed:

```c
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool is_hex(uint8_t c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}

uint64_t hexdigits(const uint8_t *buf, size_t len) {
    uint64_t n = 0;
    for (size_t i = 0; i < len; i++) n += is_hex(buf[i]);
    return n;
}
```

It is also the baseline: the harness compiles it with `clang -O3 -mcpu=native` and a
solution has to beat that. So write the C the way a good C programmer would. A
reference that is accidentally slow makes the assembly look better than it is. (This
project's word counter first used `int` where `bool` lets clang vectorize twice as
well; the claimed speed-up dropped from 20x to 11x when that was fixed. Prefer the
honest number.)

If your function exists in another language, translate it to C faithfully, or ask your
agent to and review the translation.

The three shapes:

```c
uint64_t f(const uint8_t *buf, size_t len);                  // bytes_to_u64
size_t   f(const uint8_t *src, size_t len, uint8_t *dst);    // bytes_to_bytes
uint64_t f(uint64_t a, uint64_t b, ...);                     // ints_to_u64, 1 to 4 arguments
```

For `bytes_to_bytes`, `gen.c` also defines `va_out_cap(len)`: the exact capacity of
`dst`. The fuzzer gives the candidate that many bytes and not one more.

## 3. `gen.c`: inputs that try to break it

The fuzzer is only as good as the inputs it can reach. `gen.c` defines "flavors":

- **Flavor 0 is the typical input.** Benchmarks use it unless a case says otherwise.
- **The other flavors are adversarial.** Ask: what would a vectorized implementation
  get wrong? Then generate exactly that.

Patterns that have earned their place in this repository:

| flavor | catches |
|---|---|
| everything matches / nothing matches | per-lane counters that overflow; early-exit paths |
| the densest possible input (`x x x x ...`) | counters again: this found a real bug |
| bytes adjacent to the interesting ones (`0x08`, `0x0E` next to whitespace) and their high-bit twins (`0x89`, `0xA0`) | range checks off by one; signed comparisons |
| valid data with exactly one defect, placed near the end or on a 16/64-byte boundary | validators that mishandle block edges and tails |
| data cut off mid-item at the very end | tail handling |
| uniformly random bytes | everything you did not think of |

`vibeasm/kit/va_kit.h` has the helpers (`va_range`, `va_below`, `va_chance`,
`va_fill_random`, `va_fill_from`). The harness already varies length, alignment and
guard-page placement for you, and tests every length up to 17,000 with every flavor.

## 4. `task.json`: how it is judged

```json
{
  "name": "hexdigits",
  "symbol": "hexdigits",
  "shape": "bytes_to_u64",
  "summary": "count ASCII hex digits in a buffer",
  "goal_speedup": 4.0,
  "bench": [
    {"name": "16 B", "size": 16},
    {"name": "256 B", "size": 256},
    {"name": "4 KiB", "size": 4096},
    {"name": "1 MiB", "size": 1048576}
  ]
}
```

- **Include small sizes.** Real callers pass short buffers, and a solution that is 20x
  faster on a megabyte and 2x slower on 16 bytes is not what you want. The score is the
  geometric mean over all cases.
- `goal_speedup` is where the agent loop stops early. Set it high; the loop also stops
  when rounds run out.
- Optional: `"cflags"` for `ref.c` (`mandelbrot` uses `-ffp-contract=off`),
  `"forbid_constants"` for answers that must not be looked up, `"rivals"` for expert
  implementations to time against, `"fuzz"` to change the fuzz profile.

## 5. Check the task before spending tokens on it

The compiler's own output for `ref.c` must pass the gates. If it does not, the task is
wrong, not the candidate:

```
bin/vibeasm baseline hexdigits > /tmp/compiler.s
bin/vibeasm check hexdigits /tmp/compiler.s --full
```

Then try to break your own tests: write a quick wrong version of the function and make
sure the check rejects it. `tests/zoo/` has examples of the bugs worth trying.

## 6. Run it

```
bin/vibeasm run hexdigits                  # an agent writes the assembly, verified every round
bin/vibeasm work hexdigits                 # or: get a work directory and write it yourself
bin/vibeasm brief hexdigits --oneshot      # or: print a brief to paste into any chat model
```
