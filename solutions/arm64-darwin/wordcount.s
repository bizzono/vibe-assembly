// wordcount -- count whitespace-separated words in a byte buffer
// uint64_t wordcount(const uint8_t *buf, size_t len);
//
// W = 1 for whitespace, 0 otherwise, W[-1] = 1.
// T = number of i with W[i-1] != W[i] (transitions).  They alternate
// start, end, start, ... so words = (T + 1) >> 1.
// Per 16 bytes: one 3-register tbl classifies (48-entry table, out of range -> 0),
// ext(prevW, W, #15) shifts in the previous byte, uaba accumulates |Wsh - W|.
    .text
    .globl  _wordcount

.macro CLASSIFY dst, src
    tbl     \dst\().16b, {v16.16b, v17.16b, v18.16b}, \src\().16b
.endm

// 16-byte steps while a whole vector fits, then one overlapping masked vector.
// in: x0 = cur, x2 = end, v19 = prevW, v4 = byte accumulator. clobbers x3, x9, x10
.macro TAIL
    sub     x3, x2, #16
    cmp     x0, x3
    b.hi    2f
1:
    ldr     q0, [x0], #16
    CLASSIFY v1, v0
    ext     v2.16b, v19.16b, v1.16b, #15
    mov     v19.16b, v1.16b
    uaba    v4.16b, v2.16b, v1.16b
    cmp     x0, x3
    b.ls    1b
2:
    subs    x9, x2, x0              // r = bytes left, 0..15
    b.eq    3f
    ldur    q0, [x2, #-16]
    ldur    q2, [x2, #-17]
    add     x10, x11, x9
    ldr     q3, [x10, #48]          // lanes >= 16-r are 0xFF
    CLASSIFY v1, v0
    CLASSIFY v28, v2
    eor     v2.16b, v28.16b, v1.16b
    and     v2.16b, v2.16b, v3.16b
    add     v4.16b, v4.16b, v2.16b
3:
.endm

    .p2align 4
_wordcount:
    cmp     x1, #16
    b.lo    Lsmall
    adrp    x11, Ltab@PAGE
    add     x11, x11, Ltab@PAGEOFF
    ldp     q16, q17, [x11]
    ldr     q18, [x11, #32]
    movi    v19.16b, #1
    b.hi    Lgeneral
    // exactly 16 bytes
    ldr     q0, [x0]
    CLASSIFY v1, v0
    ext     v2.16b, v19.16b, v1.16b, #15
    bic     v2.16b, v2.16b, v1.16b
    addv    b0, v2.16b
    fmov    w0, s0
    ret

Lgeneral:
    movi    v4.16b, #0
    add     x2, x0, x1
    cmp     x1, #64
    b.hs    Lbig
    TAIL
    uaddlv  h0, v4.16b
    fmov    w0, s0
    add     w0, w0, #1
    lsr     w0, w0, #1
    ret

Lbig:
    mov     x8, #1
    movi    v5.16b, #0
    movi    v6.16b, #0
    movi    v7.16b, #0
    mov     w10, #251               // 251 + 3 tail steps + 1 masked tail vector <= 255 per lane
Louter:
    sub     x9, x2, x0
    lsr     x9, x9, #6
    cmp     x9, x10
    csel    x9, x9, x10, lo
    .p2align 4
Linner:
    ldp     q0, q1, [x0]
    ldp     q2, q3, [x0, #32]
    add     x0, x0, #64
    CLASSIFY v20, v0
    CLASSIFY v21, v1
    CLASSIFY v22, v2
    CLASSIFY v23, v3
    ext     v24.16b, v19.16b, v20.16b, #15
    ext     v25.16b, v20.16b, v21.16b, #15
    ext     v26.16b, v21.16b, v22.16b, #15
    ext     v27.16b, v22.16b, v23.16b, #15
    mov     v19.16b, v23.16b
    uaba    v4.16b, v24.16b, v20.16b
    uaba    v5.16b, v25.16b, v21.16b
    uaba    v6.16b, v26.16b, v22.16b
    uaba    v7.16b, v27.16b, v23.16b
    subs    x9, x9, #1
    b.ne    Linner
    sub     x9, x2, x0
    cmp     x9, #64
    b.lo    Lafter
    uaddlp  v24.8h, v4.16b
    uadalp  v24.8h, v5.16b
    uadalp  v24.8h, v6.16b
    uadalp  v24.8h, v7.16b
    uaddlv  s24, v24.8h
    fmov    w9, s24
    add     x8, x8, x9
    movi    v4.16b, #0
    movi    v5.16b, #0
    movi    v6.16b, #0
    movi    v7.16b, #0
    b       Louter
Lafter:
    TAIL
    uaddlp  v24.8h, v4.16b
    uadalp  v24.8h, v5.16b
    uadalp  v24.8h, v6.16b
    uadalp  v24.8h, v7.16b
    uaddlv  s24, v24.8h
    fmov    w9, s24
    add     x0, x8, x9              // x8 already carries the +1
    lsr     x0, x0, #1
    ret

Lsmall:
    mov     x8, #0
    cbz     x1, Lsret
    mov     w10, #1                 // previous byte was whitespace
    mov     w13, #0x20
Lsloop:
    ldrb    w9, [x0], #1
    sub     w11, w9, #9
    cmp     w11, #5
    ccmp    w9, w13, #4, hs         // eq <=> whitespace
    cset    w11, eq
    bic     w12, w10, w11
    add     x8, x8, x12
    mov     w10, w11
    subs    x1, x1, #1
    b.ne    Lsloop
Lsret:
    mov     x0, x8
    ret

    .section __TEXT,__const
    .p2align 4
Ltab:
    .byte   0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 0
    .fill   16, 1, 0
    .byte   1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
Lmask:
    .fill   16, 1, 0
    .fill   16, 1, 0xff
