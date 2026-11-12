# Target sheet: arm64-linux (AArch64, Linux ELF AAPCS64)

AArch64 assembly, assembled by clang into an ELF object.
The calling convention is standard AAPCS64.

## Registers

| registers        | role                                   | across a call        |
|------------------|----------------------------------------|----------------------|
| `x0`-`x7`        | arguments; `x0` is the return value    | caller-saved         |
| `x8`-`x17`       | scratch                                | caller-saved         |
| `x18`            | **platform register: never use**       | -                    |
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
- Note: standard AAPCS64 on Linux does **not** guarantee a red zone below `sp`. Always allocate stack space (`sub sp, sp, #N` or `stp ..., [sp, #-N]!`) before writing to the stack.

## File skeleton

```
    .text
    .globl  myfunc               // ELF symbols have NO leading underscore
    .type   myfunc, %function
    .p2align 4
myfunc:
    ...
    ret

    .section .rodata,"a",@progbits // read-only constants (the only data you may have)
    .p2align 4
.Lmy_table:
    .byte   1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16

    .section .note.GNU-stack,"",@progbits
```

- Load the address of a constant with an `adrp` / `:lo12:` pair:
  `adrp x9, .Lmy_table` then `add x9, x9, :lo12:.Lmy_table`
  (or fold the offset into the load: `ldr q0, [x9, :lo12:.Lmy_table]`).
- Local labels should start with `.L` so the assembler does not emit them into the symbol table.
- Not available here: `.data`, `.bss`, `.comm`, `.arch`, `.cpu`, `.arch_extension`,
  `.include`, `.incbin`, and any external symbol.

## Instructions you may assume

ARMv8.2-A integer and FP, Advanced SIMD (NEON), CRC32 (`crc32b/h/w/x` and `crc32cb/h/w/x`),
AES (`aese`, `aesmc`), PMULL (`pmull`, `pmull2`), DotProd (`udot`, `sdot`), FP16, LSE atomics.
