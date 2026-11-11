// tramp_arm64_darwin.s -- the ABI-checking call trampoline (arm64, Apple platforms).
//
//   uint64_t va_tramp(void *fn, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3,
//                     uint64_t *violations, uint64_t poison);
//
// Calls fn(a0, a1, a2, a3) the way a hostile-but-legal caller would:
//
//   * every callee-saved register (x19-x28, low halves of v8-v15) holds a known
//     canary, and is compared after the call;
//   * every caller-saved register the function is not given (x4-x15, x17, v0-v7,
//     v16-v31, NZCV) is filled with garbage first, so code that "happens to work"
//     because a scratch register was zero does not work here;
//   * sp and x29 are compared after the call.
//
// *violations receives a bit mask:
//   bits 0-9    x19..x28 not preserved
//   bits 10-17  d8..d15 not preserved
//   bit 20      sp not restored
//   bit 21      x29 (frame pointer) not preserved
//
// x18 is reserved by the platform and cannot be checked at run time (the kernel may
// change it); the static lint rejects any use of it instead.

    .text
    .globl  _va_tramp
    .p2align 4

.macro VA_CHECK_X reg, idx
    add     x14, x13, #(\idx * 0x111)
    cmp     \reg, x14
    b.eq    9f
    orr     x12, x12, #(1 << \idx)
9:
.endm

.macro VA_CHECK_D reg, idx
    add     x14, x13, #(\idx * 0x111)
    fmov    x15, \reg
    cmp     x15, x14
    b.eq    9f
    orr     x12, x12, #(1 << (\idx + 10))
9:
.endm

_va_tramp:
    stp     x29, x30, [sp, #-16]!
    mov     x29, sp
    sub     sp, sp, #176
    stp     x19, x20, [sp, #0]
    stp     x21, x22, [sp, #16]
    stp     x23, x24, [sp, #32]
    stp     x25, x26, [sp, #48]
    stp     x27, x28, [sp, #64]
    stp     d8,  d9,  [sp, #80]
    stp     d10, d11, [sp, #96]
    stp     d12, d13, [sp, #112]
    stp     d14, d15, [sp, #128]
    str     x5, [sp, #144]                  // violations*
    str     x6, [sp, #152]                  // poison

    adrp    x9, _va_saved_sp@PAGE           // remember sp for the post-call check
    mov     x10, sp
    str     x10, [x9, _va_saved_sp@PAGEOFF]

    mov     x16, x0                         // fn
    mov     x0, x1
    mov     x1, x2
    mov     x2, x3
    mov     x3, x4

    // canaries in every callee-saved register
    add     x19, x6, #(0 * 0x111)
    add     x20, x6, #(1 * 0x111)
    add     x21, x6, #(2 * 0x111)
    add     x22, x6, #(3 * 0x111)
    add     x23, x6, #(4 * 0x111)
    add     x24, x6, #(5 * 0x111)
    add     x25, x6, #(6 * 0x111)
    add     x26, x6, #(7 * 0x111)
    add     x27, x6, #(8 * 0x111)
    add     x28, x6, #(9 * 0x111)
    fmov    d8,  x19
    fmov    d9,  x20
    fmov    d10, x21
    fmov    d11, x22
    fmov    d12, x23
    fmov    d13, x24
    fmov    d14, x25
    fmov    d15, x26

    // garbage in everything the callee may not rely on
    mvn     x9, x6
    dup     v0.2d,  x9
    dup     v1.2d,  x9
    dup     v2.2d,  x9
    dup     v3.2d,  x9
    dup     v4.2d,  x9
    dup     v5.2d,  x9
    dup     v6.2d,  x9
    dup     v7.2d,  x9
    dup     v16.2d, x9
    dup     v17.2d, x9
    dup     v18.2d, x9
    dup     v19.2d, x9
    dup     v20.2d, x9
    dup     v21.2d, x9
    dup     v22.2d, x9
    dup     v23.2d, x9
    dup     v24.2d, x9
    dup     v25.2d, x9
    dup     v26.2d, x9
    dup     v27.2d, x9
    dup     v28.2d, x9
    dup     v29.2d, x9
    dup     v30.2d, x9
    dup     v31.2d, x9
    msr     nzcv, x9
    mov     x4, x9
    mov     x5, x9
    mov     x6, x9
    mov     x7, x9
    mov     x8, x9
    mov     x10, x9
    mov     x11, x9
    mov     x12, x9
    mov     x13, x9
    mov     x14, x9
    mov     x15, x9
    mov     x17, x9

    blr     x16

    // ---- post-call checks (x0 holds the result; do not touch it) ----
    mov     x12, #0                         // violation mask
    adrp    x9, _va_saved_sp@PAGE
    ldr     x10, [x9, _va_saved_sp@PAGEOFF]
    mov     x11, sp
    cmp     x10, x11
    b.eq    1f
    orr     x12, x12, #(1 << 20)            // sp not restored
    mov     sp, x10
1:
    add     x11, x10, #176
    cmp     x29, x11
    b.eq    2f
    orr     x12, x12, #(1 << 21)            // frame pointer clobbered
    mov     x29, x11
2:
    ldr     x13, [sp, #152]                 // poison
    VA_CHECK_X x19, 0
    VA_CHECK_X x20, 1
    VA_CHECK_X x21, 2
    VA_CHECK_X x22, 3
    VA_CHECK_X x23, 4
    VA_CHECK_X x24, 5
    VA_CHECK_X x25, 6
    VA_CHECK_X x26, 7
    VA_CHECK_X x27, 8
    VA_CHECK_X x28, 9
    VA_CHECK_D d8,  0
    VA_CHECK_D d9,  1
    VA_CHECK_D d10, 2
    VA_CHECK_D d11, 3
    VA_CHECK_D d12, 4
    VA_CHECK_D d13, 5
    VA_CHECK_D d14, 6
    VA_CHECK_D d15, 7

    ldr     x9, [sp, #144]
    str     x12, [x9]

    ldp     x19, x20, [sp, #0]
    ldp     x21, x22, [sp, #16]
    ldp     x23, x24, [sp, #32]
    ldp     x25, x26, [sp, #48]
    ldp     x27, x28, [sp, #64]
    ldp     d8,  d9,  [sp, #80]
    ldp     d10, d11, [sp, #96]
    ldp     d12, d13, [sp, #112]
    ldp     d14, d15, [sp, #128]
    add     sp, sp, #176
    ldp     x29, x30, [sp], #16
    ret
