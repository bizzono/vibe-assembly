// v2: 16-lane PMULL folding (256 B per iteration), one-shot 16->1 lane
// reduction, final reduction with crc32x. Scalar crc32x for < 256 B and tails.
// uint64_t crc32_ieee(const uint8_t *buf, size_t len);
    .text
    .globl  _crc32_ieee

// lane \x: x = x * x^2048 ^ data[off]      (v24 = fold-by-2048-bits constant)
.macro FOLD x, off
    ldr     q26, [x0, #\off]
    pmull   v25.1q, \x\().1d, v24.1d
    pmull2  \x\().1q, \x\().2d, v24.2d
    eor3    \x\().16b, \x\().16b, v25.16b, v26.16b
.endm

// lanes a,b multiplied by their distance-to-end constants at [x9,#off], [x9,#off+16]
// leaves two partial values in a and b
.macro MUL2 a, b, off
    ldp     q24, q26, [x9, #\off]
    pmull   v25.1q, \a\().1d, v24.1d
    pmull2  \a\().1q, \a\().2d, v24.2d
    pmull   v27.1q, \b\().1d, v26.1d
    pmull2  \b\().1q, \b\().2d, v26.2d
    eor3    \a\().16b, \a\().16b, v25.16b, v27.16b
.endm

// hybrid-mode lane fold: v25 = fold-by-384-bytes constant
.macro FOLDH x, off
    ldr     q27, [x0, #\off]
    pmull   v26.1q, \x\().1d, v25.1d
    pmull2  \x\().1q, \x\().2d, v25.2d
    eor3    \x\().16b, \x\().16b, v26.16b, v27.16b
.endm

// two crc32x chains from 0: w14 = A over [x0-112, x0-56), w15 = B over [x0-56, x0)
.macro CHAINS
    ldp     x10, x11, [x0, #-112]
    ldp     x12, x13, [x0, #-56]
    crc32x  w14, wzr, x10
    crc32x  w15, wzr, x12
    crc32x  w14, w14, x11
    crc32x  w15, w15, x13
    ldp     x10, x11, [x0, #-96]
    ldp     x12, x13, [x0, #-40]
    crc32x  w14, w14, x10
    crc32x  w15, w15, x12
    crc32x  w14, w14, x11
    crc32x  w15, w15, x13
    ldp     x10, x11, [x0, #-80]
    ldp     x12, x13, [x0, #-24]
    crc32x  w14, w14, x10
    crc32x  w15, w15, x12
    crc32x  w14, w14, x11
    crc32x  w15, w15, x13
    ldr     x10, [x0, #-64]
    ldr     x12, [x0, #-8]
    crc32x  w14, w14, x10
    crc32x  w15, w15, x12
.endm

    .p2align 4
_crc32_ieee:
    cmp     x1, #16
    b.ne    Lgeneral
    ldp     x9, x10, [x0]
    mov     w8, #-1
    crc32x  w8, w8, x9
    crc32x  w8, w8, x10
    mvn     w0, w8
    ret

Lgeneral:
    mov     w8, #-1
    cmp     x1, #256
    b.lo    Lscalar
    b.eq    L256

    ldp     q0, q1, [x0]
    ldp     q2, q3, [x0, #32]
    ldp     q4, q5, [x0, #64]
    ldp     q6, q7, [x0, #96]
    ldp     q16, q17, [x0, #128]
    ldp     q18, q19, [x0, #160]
    ldp     q20, q21, [x0, #192]
    ldp     q22, q23, [x0, #224]
    fmov    s25, w8
    eor     v0.16b, v0.16b, v25.16b
    adrp    x9, Lconsts@PAGE
    add     x9, x9, Lconsts@PAGEOFF
    add     x0, x0, #256
    sub     x1, x1, #256
    cmp     x1, #384
    b.lo    Lplain
// Hybrid mode. The buffer is cut into 384 B blocks: 272 B in 17 PMULL lanes
// (lane 16 = v24) followed by 112 B that go through two scalar crc32x chains
// (A, B: 56 B each, started from 0). x0 = start of the next block; the chain
// results are xored into the first bytes of that block (lane 0's new data).
    ldr     q24, [x0]
    add     x0, x0, #128
    sub     x1, x1, #128
    ldr     q25, [x9, #256]
    ldr     q30, [x9, #272]
    cmp     x1, #640
    b.lo    Ltrans
    .p2align 4
Lhyb:
    CHAINS
    FOLDH   v1, 16
    FOLDH   v2, 32
    FOLDH   v3, 48
    FOLDH   v4, 64
    FOLDH   v5, 80
    FOLDH   v6, 96
    FOLDH   v7, 112
    FOLDH   v16, 128
    FOLDH   v17, 144
    FOLDH   v18, 160
    FOLDH   v19, 176
    FOLDH   v20, 192
    FOLDH   v21, 208
    FOLDH   v22, 224
    FOLDH   v23, 240
    FOLDH   v24, 256
    FOLDH   v0, 0
    fmov    s28, w14
    fmov    s29, w15
    pmull   v28.1q, v28.1d, v30.1d
    eor3    v0.16b, v0.16b, v28.16b, v29.16b
    add     x0, x0, #384
    sub     x1, x1, #384
    cmp     x1, #640
    b.hs    Lhyb
// leave hybrid mode: the last 256+ bytes go into 16 lanes; lane 16 is folded
// 128 B forward onto the new lane 0.
Ltrans:
    CHAINS
    FOLDH   v1, 16
    FOLDH   v2, 32
    FOLDH   v3, 48
    FOLDH   v4, 64
    FOLDH   v5, 80
    FOLDH   v6, 96
    FOLDH   v7, 112
    FOLDH   v16, 128
    FOLDH   v17, 144
    FOLDH   v18, 160
    FOLDH   v19, 176
    FOLDH   v20, 192
    FOLDH   v21, 208
    FOLDH   v22, 224
    FOLDH   v23, 240
    FOLDH   v0, 0
    ldr     q27, [x9, #112]
    pmull   v26.1q, v24.1d, v27.1d
    pmull2  v24.1q, v24.2d, v27.2d
    eor3    v0.16b, v0.16b, v26.16b, v24.16b
    fmov    s28, w14
    fmov    s29, w15
    pmull   v28.1q, v28.1d, v30.1d
    eor3    v0.16b, v0.16b, v28.16b, v29.16b
    add     x0, x0, #256
    sub     x1, x1, #256
Lplain:
    cmp     x1, #256
    b.lo    Lreduce
    ldr     q24, [x9, #240]
    .p2align 4
Lloop:
    FOLD    v0, 0
    FOLD    v1, 16
    FOLD    v2, 32
    FOLD    v3, 48
    FOLD    v4, 64
    FOLD    v5, 80
    FOLD    v6, 96
    FOLD    v7, 112
    FOLD    v16, 128
    FOLD    v17, 144
    FOLD    v18, 160
    FOLD    v19, 176
    FOLD    v20, 192
    FOLD    v21, 208
    FOLD    v22, 224
    FOLD    v23, 240
    add     x0, x0, #256
    sub     x1, x1, #256
    cmp     x1, #256
    b.hs    Lloop

Lreduce:
    MUL2    v0, v1, 0
    MUL2    v2, v3, 32
    MUL2    v4, v5, 64
    MUL2    v6, v7, 96
    MUL2    v16, v17, 128
    MUL2    v18, v19, 160
    MUL2    v20, v21, 192
    ldr     q24, [x9, #224]
    pmull   v25.1q, v22.1d, v24.1d
    pmull2  v22.1q, v22.2d, v24.2d
    eor3    v0.16b, v0.16b, v1.16b, v2.16b
    eor3    v3.16b, v3.16b, v4.16b, v5.16b
    eor3    v6.16b, v6.16b, v7.16b, v16.16b
    eor3    v17.16b, v17.16b, v18.16b, v19.16b
    eor3    v20.16b, v20.16b, v21.16b, v22.16b
    eor3    v0.16b, v0.16b, v3.16b, v6.16b
    eor3    v17.16b, v17.16b, v20.16b, v23.16b
    eor3    v0.16b, v0.16b, v17.16b, v25.16b
    fmov    x9, d0
    mov     x10, v0.d[1]
    mov     w8, #0
    crc32x  w8, w8, x9
    crc32x  w8, w8, x10
    cbz     x1, Ldone

Lscalar:
    subs    x1, x1, #8
    b.lo    2f
1:  ldr     x9, [x0], #8
    crc32x  w8, w8, x9
    subs    x1, x1, #8
    b.hs    1b
2:  tbz     x1, #2, 3f
    ldr     w9, [x0], #4
    crc32w  w8, w8, w9
3:  tbz     x1, #1, 4f
    ldrh    w9, [x0], #2
    crc32h  w8, w8, w9
4:  tbz     x1, #0, Ldone
    ldrb    w9, [x0]
    crc32b  w8, w8, w9
Ldone:
    mvn     w0, w8
    ret

// exactly 256 B: 12 PMULL lanes over [0,192) reduced in one shot to the last
// 16 B position, one scalar crc32x chain over [192,256), xor of the two.
    .p2align 4
L256:
    ldp     x10, x11, [x0, #192]
    ldp     x12, x13, [x0, #208]
    crc32x  w14, wzr, x10
    ldp     q0, q1, [x0]
    crc32x  w14, w14, x11
    ldp     q2, q3, [x0, #32]
    crc32x  w14, w14, x12
    ldp     x10, x11, [x0, #224]
    crc32x  w14, w14, x13
    ldp     x12, x13, [x0, #240]
    crc32x  w14, w14, x10
    ldp     q4, q5, [x0, #64]
    crc32x  w14, w14, x11
    ldp     q6, q7, [x0, #96]
    crc32x  w14, w14, x12
    ldp     q16, q17, [x0, #128]
    crc32x  w14, w14, x13
    ldp     q18, q19, [x0, #160]
    fmov    s25, w8
    eor     v0.16b, v0.16b, v25.16b
    adrp    x9, Lconsts@PAGE
    add     x9, x9, Lconsts@PAGEOFF
    MUL2    v0, v1, 0
    MUL2    v2, v3, 32
    MUL2    v4, v5, 64
    MUL2    v6, v7, 96
    MUL2    v16, v17, 128
    MUL2    v18, v19, 160
    eor3    v0.16b, v0.16b, v1.16b, v2.16b
    eor3    v3.16b, v3.16b, v4.16b, v5.16b
    eor3    v6.16b, v6.16b, v7.16b, v16.16b
    eor3    v17.16b, v17.16b, v18.16b, v19.16b
    eor3    v0.16b, v0.16b, v3.16b, v6.16b
    eor     v0.16b, v0.16b, v17.16b
    fmov    x9, d0
    mov     x10, v0.d[1]
    crc32x  w8, wzr, x9
    crc32x  w8, w8, x10
    eon     w0, w8, w14
    ret

    .section __TEXT,__const
    .p2align 4
// entry for distance D = 128*t bits: { x^(D+31) mod P, x^(D-33) mod P } (reflected)
Lconsts:
    .quad   0x0077f00d, 0x1f0c2cdd      // t=15  (lane 0)
    .quad   0x4a28bd43, 0xfe807bbd      // t=14
    .quad   0x682bdd4f, 0x3c656ced      // t=13
    .quad   0x596c8d81, 0xf5e48c85      // t=12
    .quad   0x5a1bb05d, 0xd1df2327      // t=11
    .quad   0xe3543be0, 0x9026d5b1      // t=10
    .quad   0x26b70c3d, 0x3f41287a      // t=9
    .quad   0x33fff533, 0x910eeec1      // t=8
    .quad   0x31f8303f, 0x0cbec0ed      // t=7
    .quad   0xdf068dc2, 0x57c54819      // t=6
    .quad   0x1c279815, 0xae0b5394      // t=5
    .quad   0x8f352d95, 0x1d9513d7      // t=4
    .quad   0x3db1ecdc, 0xaf449247      // t=3
    .quad   0xf1da05aa, 0x81256527      // t=2
    .quad   0xae689191, 0xccaa009e      // t=1  (lane 14)
    .quad   0xce3371cb, 0xe95c1271      // t=16 (loop fold)
    .quad   0x2ce423f1, 0xd31343ea      // t=24 (hybrid loop fold, 384 B)
    .quad   0x1d9513d7, 0               // x^(448+31): chain A forward 56 B
