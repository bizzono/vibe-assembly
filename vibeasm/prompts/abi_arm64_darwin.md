# Target sheet: arm64-darwin (Apple Silicon, macOS)

AArch64 assembly, assembled by clang's integrated assembler into a Mach-O object.
The calling convention is AAPCS64 with Apple's changes.

## Registers

| registers        | role                                   | across a call        |
|------------------|----------------------------------------|----------------------|
| `x0`-`x7`        | arguments; `x0` is the return value    | caller-saved         |
| `x8`-`x17`       | scratch                                | caller-saved         |
| `x18`            | **reserved by the platform: never use**| -                    |
| `x19`-`x28`      | general purpose                        | **callee-saved**     |
| `x29` (fp)       | frame pointer                          | **callee-saved**     |
| `x30` (lr)       | return address                         | you need it to `ret` |
| `sp`             | stack pointer, 16-byte aligned         | **must be restored** |
| `v0`-`v7`        | FP/SIMD arguments and scratch          | caller-saved         |
| `v8`-`v15`       | FP/SIMD                                | **low 64 bits (`d8`-`d15`) callee-saved** |
| `v16`-`v31`      | FP/SIMD scratch                        | caller-saved         |
| NZCV flags       |                                        | caller-saved         |
| FPCR             | rounding mode etc.                     | do not change        |

- `wN` is the low 32 bits of `xN`; writing `wN` zeroes the upper 32 bits.
- Integer arguments arrive in `x0, x1, x2, ...` in order; the result leaves in `x0`.
- A leaf function that uses only `x0`-`x17` and `v0`-`v7`, `v16`-`v31` needs no stack
  frame at all. This is the cheapest and safest shape: prefer it.
- If you need more registers, save and restore callee-saved ones in pairs and keep `sp`
  16-byte aligned:

  ```
      stp     x19, x20, [sp, #-32]!
      stp     d8,  d9,  [sp, #16]
      ...
      ldp     d8,  d9,  [sp, #16]
      ldp     x19, x20, [sp], #32
      ret
  ```
- Apple platforms guarantee a 128-byte **red zone**: a leaf function may use the 128
  bytes below `sp` as scratch without moving `sp`.
- On Apple platforms using a misaligned `sp` as a base register faults.

## File skeleton

```
    .text
    .globl  _myfunc              // C symbol `myfunc` is `_myfunc` in assembly
    .p2align 4
_myfunc:
    ...
    ret

    .section __TEXT,__const      // read-only constants (the only data you may have)
    .p2align 4
my_table:
    .byte   1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
```

- Load the address of a constant with a page/offset pair:
  `adrp x9, my_table@PAGE` then `add x9, x9, my_table@PAGEOFF`
  (or fold the offset into the load: `ldr q0, [x9, my_table@PAGEOFF]`).
- Comments are `//` or `;`. Immediates are written `#42`, `#0x2a`.
- Labels: any name followed by `:`. Numeric local labels (`1:` ... `b 1b` / `b 1f`)
  work. Only the function's own label may be `.globl`.
- `.p2align n` aligns to 2^n bytes. Aligning hot loop heads (`.p2align 4`) sometimes
  helps and sometimes hurts: measure.
- Macros: `.macro name a, b` ... `\a` ... `.endm`; repetition: `.rept n` ... `.endr`;
  constants: `.equ NAME, value`.
- Data directives: `.byte`, `.short` (2 bytes), `.long` (4), `.quad` (8), `.ascii "..."`,
  `.fill count, size, value`.
- Not available here: `.data`, `.bss`, `.comm`, `.arch`, `.cpu`, `.arch_extension`,
  `.include`, `.incbin`, and any external symbol.

## Instructions you may assume

Everything in the baseline for this target: ARMv8.4-A integer and FP, Advanced SIMD
(NEON), CRC32 (`crc32b/h/w/x` and `crc32cb/h/w/x`), AES (`aese`, `aesmc`, ...), PMULL
(`pmull`, `pmull2`: 64x64 -> 128 carry-less multiply), SHA1, SHA256, SHA512, SHA3 (`eor3`,
`bcax`, `rax1`, `xar`), DotProd (`udot`, `sdot`), half-precision FP, LSE atomics, RDM.

**Not** available: SVE, SVE2, SME. The assembler will reject them.

## Things that bite

- **Loads fault.** A 16-byte vector load that touches even one byte past the end of the
  buffer can cross into an unmapped page. The test harness guarantees it will. For
  a tail of fewer than 16 bytes either loop over bytes, or (when the buffer is at least
  16 bytes long) reload the *last* 16 bytes of the buffer, overlapping what you already
  processed, and mask out or otherwise account for the overlap.
- Loads before the start of the buffer fault the same way (so no rounding the pointer
  down to an alignment boundary and loading from there).
- `len == 0` means the pointer may not be dereferenced at all.
- Unsigned conditions are `hi/hs/lo/ls`; signed are `gt/ge/lt/le`. Bytes above `0x7F`
  compared as signed is the classic bug.
- NEON comparisons (`cmeq`, `cmhi`, `cmhs`, `cmgt`...) produce all-ones (`0xFF`) lanes for
  true. `sub acc, acc, mask` therefore adds 1 per true lane. A byte-lane accumulator
  overflows after 255 additions: widen it (`uaddlp`, `uadalp`, `uaddlv`) before that.
- Horizontal reductions: `addv`, `uaddlv` (widening sum), `umaxv`/`uminv` ("any"/"all").
- A cheap "movemask" for a byte mask: `shrn v0.8b, v0.8h, #4` then `fmov x9, d0` gives 4
  bits per input byte; `rbit` + `clz` or `ctz`-style tricks find the first set lane.
- `tbl` with an out-of-range index yields 0; `tbx` leaves the destination lane unchanged.
  `tbl` can index a table of up to four consecutive registers
  (`tbl v0.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v1.16b`).
- Arithmetic immediates are 12 bits (optionally shifted left by 12). Logical immediates
  (`and`, `orr`, `eor`, `tst`) must be a repeating bit-mask pattern; anything else needs
  the constant in a register (`mov` / `movk`).
- `mov xN, #imm` only assembles when one instruction can encode it. Build wide constants
  with `movz`/`movk` (`mov x9, #0x1234` then `movk x9, #0x5678, lsl #16`, ...) or load
  them from `__TEXT,__const`.
- `ret` returns through `x30`. If you `bl` anywhere, save `x29`/`x30` first.
