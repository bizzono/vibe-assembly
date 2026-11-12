// mandelbrot -- total escape-time iterations over a Mandelbrot grid (IEEE doubles, bit-exact)
// uint64_t mandelbrot(uint64_t width, uint64_t height, uint64_t max_iter);
//
// Approach:
//  * 8 pixels of a row at a time: 4 NEON vectors of 2 doubles, all in flight together.
//    Each lane has a sticky "still active" mask; count += active each iteration.
//    A block ends when every lane is inactive or max_iter is reached.
//  * Row mirroring: row py and row h-py have ci of opposite sign whenever
//    ci(py) + ci(h-py) == 0 exactly (checked at run time, per row). The iteration
//    is exactly sign-symmetric in zi/ci, so the counts are identical: compute one
//    row and count it twice.
//
// Registers:
//   x8 width, x1 height, x2 max_iter, x0 total, x9 py, x11 row weight,
//   x12 px of block start, x13 iterations left
//   v0-v3 zr, v4-v7 zi, v16-v19 cr, v20-v23 active, v24/v25 counts (per row)
//   v26-v28 temps, v29 4.0, v30 ci, v31 dx, v8 px (ints), v9 width, v10 -2.0,
//   v11 int 2, d12 dy, d13 -1.5, v14 {0,1}

    .macro STEP zr, zi, cr, act, cnt
    fmul    v26.2d, \zr\().2d, \zr\().2d        // zr2
    fmul    v27.2d, \zi\().2d, \zi\().2d        // zi2
    fadd    v28.2d, \zr\().2d, \zr\().2d        // 2*zr
    fmul    v28.2d, v28.2d, \zi\().2d           // 2*zr*zi
    fadd    \zi\().2d, v28.2d, v30.2d           // + ci
    fsub    v28.2d, v26.2d, v27.2d              // zr2 - zi2
    fadd    \zr\().2d, v28.2d, \cr\().2d        // + cr
    fadd    v26.2d, v26.2d, v27.2d              // zr2 + zi2
    fcmge   v26.2d, v29.2d, v26.2d              // 4 >= mag  (false for NaN)
    and     \act\().16b, \act\().16b, v26.16b   // sticky
    sub     \cnt\().2d, \cnt\().2d, \act\().2d  // count += active
    .endm

    .macro INIT cr, act
    ucvtf   \cr\().2d, v8.2d
    cmhi    \act\().2d, v9.2d, v8.2d            // px < width
    add     v8.2d, v8.2d, v11.2d
    fmul    \cr\().2d, v31.2d, \cr\().2d
    fadd    \cr\().2d, \cr\().2d, v10.2d
    .endm

    .text
    .globl  _mandelbrot
    .p2align 4
_mandelbrot:
    mov     x8, x0
    mov     x0, #0
    cbz     x8, Lret
    cbz     x1, Lret
    cbz     x2, Lret
    stp     d8, d9, [sp, #-64]!
    stp     d10, d11, [sp, #16]
    stp     d12, d13, [sp, #32]
    stp     d14, d15, [sp, #48]

    ucvtf   d16, x8
    fmov    d17, #3.0
    ucvtf   d18, x1
    fdiv    d16, d17, d16                       // dx
    fdiv    d12, d17, d18                       // dy
    dup     v31.2d, v16.d[0]
    fmov    d13, #-1.5
    fmov    v10.2d, #-2.0
    fmov    v29.2d, #4.0
    dup     v9.2d, x8
    mov     x10, #2
    dup     v11.2d, x10
    movi    v14.2d, #0
    mov     x10, #1
    ins     v14.d[1], x10
    mov     x9, #0

Lrow:
    ucvtf   d16, x9
    fmul    d16, d12, d16
    fadd    d16, d16, d13                       // ci
    mov     x11, #1
    cbz     x9, Ldo_row
    sub     x10, x1, x9                         // mirror row
    ucvtf   d17, x10
    fmul    d17, d12, d17
    fadd    d17, d17, d13
    fadd    d17, d17, d16
    fcmp    d17, #0.0
    b.ne    Ldo_row                             // not an exact mirror
    cmp     x9, x10
    b.eq    Ldo_row                             // the middle row
    b.hi    Lnext_row                           // already counted with its mirror
    mov     x11, #2
Ldo_row:
    dup     v30.2d, v16.d[0]
    movi    v24.2d, #0
    movi    v25.2d, #0
    mov     v8.16b, v14.16b
    mov     x12, #0

Lblock:
    INIT    v16, v20
    INIT    v17, v21
    INIT    v18, v22
    INIT    v19, v23
    movi    v0.2d, #0
    movi    v1.2d, #0
    movi    v2.2d, #0
    movi    v3.2d, #0
    movi    v4.2d, #0
    movi    v5.2d, #0
    movi    v6.2d, #0
    movi    v7.2d, #0
    mov     x13, x2
Liter:
    STEP    v0, v4, v16, v20, v24
    STEP    v1, v5, v17, v21, v25
    STEP    v2, v6, v18, v22, v24
    STEP    v3, v7, v19, v23, v25
    orr     v26.16b, v20.16b, v21.16b
    orr     v27.16b, v22.16b, v23.16b
    orr     v26.16b, v26.16b, v27.16b
    umaxv   s26, v26.4s
    fmov    w14, s26
    cbz     w14, Lblock_done
    subs    x13, x13, #1
    b.ne    Liter
Lblock_done:
    add     x12, x12, #8
    cmp     x12, x8
    b.lo    Lblock

    add     v24.2d, v24.2d, v25.2d
    addp    d24, v24.2d
    fmov    x14, d24
    madd    x0, x14, x11, x0
Lnext_row:
    add     x9, x9, #1
    cmp     x9, x1
    b.lo    Lrow

    ldp     d10, d11, [sp, #16]
    ldp     d12, d13, [sp, #32]
    ldp     d14, d15, [sp, #48]
    ldp     d8, d9, [sp], #64
Lret:
    ret
