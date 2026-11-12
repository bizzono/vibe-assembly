# Target sheet: x86_64-linux (x86-64, Linux System V AMD64 ABI)

x86-64 assembly (AT&T or `.intel_syntax noprefix`), assembled by clang into an ELF object.
The calling convention is the System V AMD64 ABI.

## Registers

| registers           | role                                   | across a call        |
|---------------------|----------------------------------------|----------------------|
| `rdi, rsi, rdx, rcx, r8, r9` | integer arguments 1..6        | caller-saved         |
| `rax`               | return value (and scratch)             | caller-saved         |
| `r10`, `r11`        | scratch                                | caller-saved         |
| `rbx`, `rbp`, `r12`-`r15` | general purpose                  | **callee-saved**     |
| `rsp`               | stack pointer (`rsp % 16 == 8` on entry) | **must be restored** |
| `xmm0`-`xmm15` / `ymm0`-`ymm15` | SIMD/FP scratch            | caller-saved         |

- Integer arguments arrive in `rdi, rsi, rdx, rcx, r8, r9`; the return value leaves in `rax`.
- A 128-byte red zone (`-128(%rsp)` .. `-1(%rsp)`) is available to leaf functions.
- If you use `ymm` (AVX2) registers, execute `vzeroupper` before `ret` if mixing with legacy SSE.

## File skeleton

```
    .text
    .globl  myfunc               // ELF symbols have NO leading underscore
    .type   myfunc, @function
    .p2align 4
myfunc:
    ...
    ret

    .section .rodata,"a",@progbits
    .p2align 5
.Lmy_table:
    .byte   1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16

    .section .note.GNU-stack,"",@progbits
```

- Address read-only constants RIP-relatively: `leaq .Lmy_table(%rip), %r8` or `vmovdqa .Lmy_table(%rip), %ymm0`.
- Local labels should start with `.L`.

## Instructions you may assume

`x86-64-v3`: SSE through SSE4.2, AVX, AVX2, BMI1, BMI2, FMA, LZCNT, MOVBE, POPCNT, PCLMULQDQ.
