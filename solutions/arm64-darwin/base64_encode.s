// base64_encode -- standard Base64 encoding (RFC 4648, with padding)
// size_t base64_encode(const uint8_t *src, size_t len, uint8_t *dst);
//
// x0 src cursor, x1 remaining, x2 dst cursor, x8 dst start, x9 table
// v16-v19 alphabet, v20 = 63, v21/v22 shuffle indices, v23/v24 shifts
//
// >=48 bytes : ld3 / shifts / 4-register tbl / st4, 48 -> 64 per iteration
// 12-byte blocks: 16-byte load, tbl shuffle, ushl, tbl; the last blocks are
//               loaded from end-16 with shifted shuffle indices (no overread)
// < 16 bytes : scalar

    .macro BLOCK idxh, idxl
    tbl     v1.16b, {v0.16b}, \idxh\().16b
    tbl     v2.16b, {v0.16b}, \idxl\().16b
    ushl    v1.16b, v1.16b, v23.16b
    ushl    v2.16b, v2.16b, v24.16b
    orr     v1.16b, v1.16b, v2.16b
    and     v1.16b, v1.16b, v20.16b
    tbl     v1.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v1.16b
    .endm

    .text
    .globl  _base64_encode
    .p2align 4
_base64_encode:
    adrp    x9, Ltab@PAGE
    add     x9, x9, Ltab@PAGEOFF
    mov     x8, x2
    cmp     x1, #16
    b.lo    Lsmall
    ld1     {v16.16b, v17.16b, v18.16b, v19.16b}, [x9]
    movi    v20.16b, #63
    cmp     x1, #48
    b.lo    Lmid

    .p2align 4
Lloop48:
    ld3     {v0.16b, v1.16b, v2.16b}, [x0], #48
    sub     x1, x1, #48
    ushr    v4.16b, v0.16b, #2
    ushr    v5.16b, v1.16b, #4
    ushr    v6.16b, v2.16b, #6
    sli     v5.16b, v0.16b, #4
    sli     v6.16b, v1.16b, #2
    and     v7.16b, v2.16b, v20.16b
    and     v5.16b, v5.16b, v20.16b
    and     v6.16b, v6.16b, v20.16b
    tbl     v4.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v4.16b
    tbl     v5.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v5.16b
    tbl     v6.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v6.16b
    tbl     v7.16b, {v16.16b, v17.16b, v18.16b, v19.16b}, v7.16b
    cmp     x1, #48
    st4     {v4.16b, v5.16b, v6.16b, v7.16b}, [x2], #64
    b.hs    Lloop48

Lmid:
    ldp     q21, q22, [x9, #64]
    ldp     q23, q24, [x9, #96]
    cmp     x1, #16
    b.lo    Llt16
L12loop:
    ldr     q0, [x0], #12
    sub     x1, x1, #12
    BLOCK   v21, v22
    cmp     x1, #16
    str     q1, [x2], #16
    b.hs    L12loop

Llt16:                              // x1 in 0..15
    add     x10, x0, x1
    sub     x10, x10, #16           // end - 16 (valid: total len >= 16)
    cmp     x1, #12
    b.lo    1f
    mov     w11, #16
    sub     w11, w11, w1            // offset of block inside the load
    ldr     q0, [x10]
    dup     v3.16b, w11
    add     v4.16b, v21.16b, v3.16b
    add     v5.16b, v22.16b, v3.16b
    BLOCK   v4, v5
    add     x0, x0, #12
    sub     x1, x1, #12
    str     q1, [x2], #16
1:                                  // x1 in 0..11
    cmp     x1, #3
    b.lo    Ltail
    add     w11, w1, w1, lsl #1
    add     w11, w11, w1, lsl #3    // 11 * rem
    lsr     w11, w11, #5            // q = rem / 3
    add     w12, w11, w11, lsl #1   // 3q
    sub     w13, w1, w12            // m = rem % 3
    mov     w14, #4
    sub     w14, w14, w13           // offset = 4 - m
    ldr     q0, [x10]
    dup     v3.16b, w14
    add     v4.16b, v21.16b, v3.16b
    add     v5.16b, v22.16b, v3.16b
    BLOCK   v4, v5
    add     x2, x2, x11, lsl #2
    add     x0, x0, x12
    mov     x1, x13
    stur    q1, [x2, #-16]

Ltail:                              // x1 in 0..2
    cbz     x1, Ldone
    ldrb    w11, [x0]
    lsr     w12, w11, #2
    ldrb    w12, [x9, x12]
    ubfiz   w13, w11, #4, #2
    strb    w12, [x2]
    cmp     x1, #1
    b.eq    Lone
    ldrb    w14, [x0, #1]
    mov     w15, #0x3d
    orr     w13, w13, w14, lsr #4
    ubfiz   w14, w14, #2, #4
    ldrb    w13, [x9, x13]
    ldrb    w14, [x9, x14]
    strb    w13, [x2, #1]
    strb    w14, [x2, #2]
    strb    w15, [x2, #3]
    add     x2, x2, #4
    sub     x0, x2, x8
    ret
Lone:
    ldrb    w13, [x9, x13]
    mov     w15, #0x3d3d
    strb    w13, [x2, #1]
    strh    w15, [x2, #2]
    add     x2, x2, #4
Ldone:
    sub     x0, x2, x8
    ret

Lsmall:                             // len < 16: scalar
    cmp     x1, #3
    b.lo    Ltail
2:
    ldrb    w11, [x0]
    ldrb    w12, [x0, #1]
    ldrb    w13, [x0, #2]
    add     x0, x0, #3
    sub     x1, x1, #3
    lsr     w14, w11, #2
    ubfiz   w11, w11, #4, #2
    orr     w11, w11, w12, lsr #4
    ubfiz   w12, w12, #2, #4
    orr     w12, w12, w13, lsr #6
    and     w13, w13, #63
    ldrb    w14, [x9, x14]
    ldrb    w11, [x9, x11]
    ldrb    w12, [x9, x12]
    ldrb    w13, [x9, x13]
    strb    w14, [x2]
    strb    w11, [x2, #1]
    strb    w12, [x2, #2]
    strb    w13, [x2, #3]
    add     x2, x2, #4
    cmp     x1, #3
    b.hs    2b
    b       Ltail

    .section __TEXT,__const
    .p2align 6
Ltab:
    .ascii  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
Lidxh:
    .byte   0, 0, 1, 2, 3, 3, 4, 5, 6, 6, 7, 8, 9, 9, 10, 11
Lidxl:
    .byte   1, 1, 2, 2, 4, 4, 5, 5, 7, 7, 8, 8, 10, 10, 11, 11
Lshh:
    .byte   -2, 4, 2, 0, -2, 4, 2, 0, -2, 4, 2, 0, -2, 4, 2, 0
Lshl:
    .byte   -8, -4, -6, -8, -8, -4, -6, -8, -8, -4, -6, -8, -8, -4, -6, -8
