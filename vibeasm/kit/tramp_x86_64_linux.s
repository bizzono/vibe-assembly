// tramp_x86_64_linux.s -- the ABI-checking call trampoline (x86_64, Linux System V ABI).
//
//   uint64_t va_tramp(void *fn, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3,
//                     uint64_t *violations, uint64_t poison);
//
// System V AMD64 ABI callee-saved registers: rbx, rbp, r12..r15, rsp.
// *violations bit mask:
//   bit 0   rbx not preserved
//   bit 1   r12 not preserved
//   bit 2   r13 not preserved
//   bit 3   r14 not preserved
//   bit 4   r15 not preserved
//   bit 20  rsp not restored
//   bit 21  rbp not preserved

    .text
    .globl  va_tramp
    .type   va_tramp, @function
    .p2align 4

va_tramp:
    pushq   %rbp
    movq    %rsp, %rbp
    subq    $64, %rsp

    movq    %rbx, 0(%rsp)
    movq    %r12, 8(%rsp)
    movq    %r13, 16(%rsp)
    movq    %r14, 24(%rsp)
    movq    %r15, 32(%rsp)
    movq    %r9,  40(%rsp)                  // violations*
    movq    16(%rbp), %rax                  // 7th arg: poison
    movq    %rax, 48(%rsp)

    movq    %rsp, va_saved_sp(%rip)

    // Canaries in callee-saved registers
    leaq    0x000(%rax), %rbx
    leaq    0x111(%rax), %r12
    leaq    0x222(%rax), %r13
    leaq    0x333(%rax), %r14
    leaq    0x444(%rax), %r15

    // Shift arguments: fn=%rdi, a0=%rsi, a1=%rdx, a2=%rcx, a3=%r8
    movq    %rdi, %r10
    movq    %rsi, %rdi
    movq    %rdx, %rsi
    movq    %rcx, %rdx
    movq    %r8,  %rcx

    // Poison caller-saved registers
    notq    %rax
    movq    %rax, %xmm0
    punpcklqdq %xmm0, %xmm0
    movdqa  %xmm0, %xmm1
    movdqa  %xmm0, %xmm2
    movdqa  %xmm0, %xmm3
    movdqa  %xmm0, %xmm4
    movdqa  %xmm0, %xmm5
    movdqa  %xmm0, %xmm6
    movdqa  %xmm0, %xmm7
    movq    %rax, %r8
    movq    %rax, %r9
    movq    %rax, %r11

    callq   *%r10

    // Post-call ABI verification (%rax holds return value)
    xorl    %r11d, %r11d
    movq    va_saved_sp(%rip), %rcx
    cmpq    %rcx, %rsp
    je      1f
    orq     $(1 << 20), %r11
    movq    %rcx, %rsp
1:
    leaq    64(%rcx), %rdx
    cmpq    %rdx, %rbp
    je      2f
    orq     $(1 << 21), %r11
    movq    %rdx, %rbp
2:
    movq    48(%rsp), %rcx                  // poison
    leaq    0x000(%rcx), %rdx
    cmpq    %rdx, %rbx
    je      3f
    orq     $(1 << 0), %r11
3:
    leaq    0x111(%rcx), %rdx
    cmpq    %rdx, %r12
    je      4f
    orq     $(1 << 1), %r11
4:
    leaq    0x222(%rcx), %rdx
    cmpq    %rdx, %r13
    je      5f
    orq     $(1 << 2), %r11
5:
    leaq    0x333(%rcx), %rdx
    cmpq    %rdx, %r14
    je      6f
    orq     $(1 << 3), %r11
6:
    leaq    0x444(%rcx), %rdx
    cmpq    %rdx, %r15
    je      7f
    orq     $(1 << 4), %r11
7:
    movq    40(%rsp), %rcx
    movq    %r11, (%rcx)

    movq    0(%rsp),  %rbx
    movq    8(%rsp),  %r12
    movq    16(%rsp), %r13
    movq    24(%rsp), %r14
    movq    32(%rsp), %r15
    addq    $64, %rsp
    popq    %rbp
    ret

    .section .note.GNU-stack,"",@progbits
