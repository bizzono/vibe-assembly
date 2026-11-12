// utf8_validate -- is this byte buffer well-formed UTF-8?
// uint64_t utf8_validate(const uint8_t *buf, size_t len);
//
// Keiser-Lemire lookup validation (3 nibble tables), stateless per 16-byte
// block: the "previous 1/2/3 bytes" vectors are simply unaligned loads at
// p-1, p-2, p-3 (the first block uses ext with zero instead).
// 64-byte chunks that are pure ASCII are skipped.
// len < 16 (and 17, 18) use a scalar loop.
//
// Constant registers:
//   v16 byte_1_high table   v17 byte_1_low table   v18 byte_2_high table
//   v19 0x0f  v20 0xdf  v21 0xef  v22 0x7f  v25 "incomplete at end" maxima
//   v23 error accumulator   v24 pending "incomplete" of last full chunk

    // prev1/2/3 in v4/v5/v6 (clobbered), current block in \cur (preserved)
    // error bits for the block are left in v7
    .macro CORE cur
    // The "2nd/3rd continuation" check is folded into the table indices:
    //   a = prev2 >= E0  poisons the byte_1_high index (sri keeps a's top
    //       nibble -> out of range -> tbx leaves the fallback 0x01 there):
    //       error iff cur is not a continuation (bit 0 of byte_2_high).
    //   b = prev3 >= F0  poisons the byte_1_low index the same way with
    //       fallback 0x80: error iff prev1 is a continuation (bit 7 of
    //       byte_1_high) and cur is not (bit 7 of byte_2_high).
    //   Where neither holds, bit 1 (prev1 in 00..BF, cur continuation) is
    //   an error as it stands. a and b together is always an invalid input
    //   and is reported two or three positions earlier.
    cmhi    v5.16b, v5.16b, v20.16b
    cmhi    v6.16b, v6.16b, v21.16b
    ushr    v27.16b, \cur\().16b, #4
    mov     v7.16b, v22.16b
    mov     v28.16b, v30.16b
    sri     v5.16b, v4.16b, #4
    bit     v6.16b, v4.16b, v19.16b
    tbl     v27.16b, {v18.16b}, v27.16b
    tbx     v7.16b, {v16.16b}, v5.16b
    tbx     v28.16b, {v17.16b}, v6.16b
    and     v7.16b, v7.16b, v27.16b
    and     v7.16b, v7.16b, v28.16b
    .endm

    // block at [x2+off], already loaded in \cur; needs x2+off-3 readable
    .macro BLOCK cur, off
    ldur    q4, [x2, #(\off - 1)]
    ldur    q5, [x2, #(\off - 2)]
    ldur    q6, [x2, #(\off - 3)]
    CORE    \cur
    orr     v23.16b, v23.16b, v7.16b
    .endm

    .macro LOADC
    adrp    x9, Ltab@PAGE
    add     x9, x9, Ltab@PAGEOFF
    ldp     q16, q17, [x9]
    ldp     q18, q25, [x9, #32]
    ldp     q19, q20, [x9, #64]
    ldp     q21, q22, [x9, #96]
    ldr     q30, [x9, #128]
    .endm

    .text
    .globl  _utf8_validate
    .p2align 4
_utf8_validate:
    cmp     x1, #16
    b.lo    Lscalar
    ldp     x10, x11, [x0]
    orr     x10, x10, x11
    tst     x10, #0x8080808080808080
    b.ne    Lfirst_full
    cmp     x1, #16
    b.eq    Lret1
    LOADC
    movi    v23.16b, #0
    movi    v24.16b, #0
    b       Ldispatch
Lfirst_full:
    ldr     q0, [x0]
    LOADC
    movi    v26.16b, #0
    ext     v4.16b, v26.16b, v0.16b, #15
    ext     v5.16b, v26.16b, v0.16b, #14
    ext     v6.16b, v26.16b, v0.16b, #13
    CORE    v0
    uqsub   v24.16b, v0.16b, v25.16b
    cmp     x1, #16
    b.ne    1f
    orr     v23.16b, v7.16b, v24.16b
    umaxv   b23, v23.16b
    fmov    w9, s23
    cmp     w9, #0
    cset    x0, eq
    ret
1:
    mov     v23.16b, v7.16b
Ldispatch:
    add     x3, x0, x1              // end
    add     x2, x0, #16
    sub     x4, x3, x2
    cmp     x4, #64
    b.lo    Ltail

Ltop:
    // ASCII test on the integer side: the validation below is bound by the
    // SIMD ports, the integer ones are idle
    ldp     x9, x10, [x2]
    ldp     x11, x12, [x2, #16]
    ldp     x13, x14, [x2, #32]
    ldp     x15, x16, [x2, #48]
    orr     x9, x9, x10
    orr     x11, x11, x12
    orr     x13, x13, x14
    orr     x15, x15, x16
    orr     x9, x9, x11
    orr     x13, x13, x15
    orr     x9, x9, x13
    tst     x9, #0x8080808080808080
    b.eq    Lascii
Lfull:
    ldp     q0, q1, [x2]
    ldp     q2, q3, [x2, #32]
    BLOCK   v0, 0
    BLOCK   v1, 16
    BLOCK   v2, 32
    BLOCK   v3, 48
    uqsub   v24.16b, v3.16b, v25.16b
    add     x2, x2, #64
    sub     x4, x3, x2
    cmp     x4, #64
    b.hs    Ltop
    b       Ltail

Lascii:
    orr     v23.16b, v23.16b, v24.16b
Lascii_loop:
    add     x2, x2, #64
    sub     x4, x3, x2
    cmp     x4, #64
    b.lo    Ltail
    ldp     q0, q1, [x2]
    ldp     q2, q3, [x2, #32]
    orr     v28.16b, v0.16b, v1.16b
    orr     v29.16b, v2.16b, v3.16b
    orr     v28.16b, v28.16b, v29.16b
    umaxv   b28, v28.16b
    fmov    w9, s28
    tbz     w9, #7, Lascii_loop
    b       Lfull

Ltail:                              // x4 = remaining (< 64)
    cmp     x4, #16
    b.lo    Ltail_last
Ltail_loop:
    ldr     q0, [x2]
    BLOCK   v0, 0
    add     x2, x2, #16
    sub     x4, x4, #16
    cmp     x4, #16
    b.hs    Ltail_loop
Ltail_last:
    cbz     x4, Lfinish
    cmp     x1, #19
    b.lo    Lscalar
    sub     x2, x3, #16
    ldr     q0, [x2]
    BLOCK   v0, 0
Lfinish:
    ldur    q0, [x3, #-16]
    uqsub   v0.16b, v0.16b, v25.16b
    orr     v23.16b, v23.16b, v0.16b
    umaxv   b23, v23.16b
    fmov    w9, s23
    cmp     w9, #0
    cset    x0, eq
    ret

// ---------------------------------------------------------------- scalar
Lscalar:
    add     x3, x0, x1
Ls_loop:
    cmp     x0, x3
    b.hs    Lret1
    ldrb    w4, [x0], #1
    tbz     w4, #7, Ls_loop
    sub     x5, x3, x0              // bytes left after the lead
    sub     w6, w4, #0xc2
    cmp     w6, #0x1d
    b.hi    Ls_3
    cbz     x5, Lret0
    ldrsb   w7, [x0], #1
    cmn     w7, #65
    b.gt    Lret0
    b       Ls_loop
Ls_3:
    and     w6, w4, #0xf0
    cmp     w6, #0xe0
    b.ne    Ls_4
    cmp     x5, #2
    b.lo    Lret0
    ldrb    w7, [x0]
    mov     w8, #0x80
    mov     w9, #0xa0
    cmp     w4, #0xe0
    csel    w8, w9, w8, eq
    mov     w9, #0xbf
    mov     w10, #0x9f
    cmp     w4, #0xed
    csel    w9, w10, w9, eq
    cmp     w7, w8
    b.lo    Lret0
    cmp     w7, w9
    b.hi    Lret0
    ldrsb   w7, [x0, #1]
    cmn     w7, #65
    b.gt    Lret0
    add     x0, x0, #2
    b       Ls_loop
Ls_4:
    sub     w6, w4, #0xf0
    cmp     w6, #4
    b.hi    Lret0
    cmp     x5, #3
    b.lo    Lret0
    ldrb    w7, [x0]
    mov     w8, #0x80
    mov     w9, #0x90
    cmp     w4, #0xf0
    csel    w8, w9, w8, eq
    mov     w9, #0xbf
    mov     w10, #0x8f
    cmp     w4, #0xf4
    csel    w9, w10, w9, eq
    cmp     w7, w8
    b.lo    Lret0
    cmp     w7, w9
    b.hi    Lret0
    ldrsb   w7, [x0, #1]
    cmn     w7, #65
    b.gt    Lret0
    ldrsb   w7, [x0, #2]
    cmn     w7, #65
    b.gt    Lret0
    add     x0, x0, #3
    b       Ls_loop
Lret1:
    mov     x0, #1
    ret
Lret0:
    mov     x0, #0
    ret

    .section __TEXT,__const
    .p2align 4
Ltab:
    // byte_1_high: indexed by high nibble of the previous byte
    .byte   0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02
    .byte   0x82, 0x82, 0x82, 0x82, 0x21, 0x01, 0x15, 0x49
    // byte_1_low: indexed by low nibble of the previous byte
    .byte   0x67, 0x23, 0x03, 0x03, 0x0b, 0x4b, 0x4b, 0x4b
    .byte   0x4b, 0x4b, 0x4b, 0x4b, 0x4b, 0x5b, 0x4b, 0x4b
    // byte_2_high: indexed by high nibble of the current byte
    .byte   0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81, 0x81
    .byte   0x66, 0x2e, 0x3a, 0x3a, 0x81, 0x81, 0x81, 0x81
    // a lead byte in the last 3 positions that needs more bytes than remain
    .byte   0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
    .byte   0xff, 0xff, 0xff, 0xff, 0xff, 0xef, 0xdf, 0xbf
    .fill   16, 1, 0x0f
    .fill   16, 1, 0xdf
    .fill   16, 1, 0xef
    .fill   16, 1, 0x01
    .fill   16, 1, 0x80
