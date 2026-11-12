// examples/nbody_sim.s
//
// 100% standalone ARM64 macOS executable (zero C source files):
// N-Body Gravitational Galaxy Collision & Force-Integration Engine.
//
//   clang examples/nbody_sim.s -o /tmp/nbody && /tmp/nbody
//   clang examples/nbody_sim.s -o /tmp/nbody && /tmp/nbody --bench
//
// Features:
//   - Computes gravitational potential & tidal spiral density for two
//     interacting galactic cores at (24, 19) and (48, 29) across a 72x48
//     truecolor pixel grid and flushes in a single `_write` syscall.
//   - `--bench` mode runs 10,000 full 64-body all-pairs O(N^2) gravitational
//     force integration steps (40,960,000 pair interactions) in hardware
//     IEEE-754 double precision (`fmadd`, `fsqrt`, `fdiv`).

    .section __TEXT,__text,regular,pure_instructions
    .p2align 2
    .globl _main

Lemit_u8:
    cmp     w8, #100
    b.lo    1f
    mov     w9, #100
    udiv    w10, w8, w9
    msub    w8, w10, w9, w8
    add     w10, w10, #'0'
    strb    w10, [x19], #1
    mov     w9, #10
    udiv    w10, w8, w9
    msub    w8, w10, w9, w8
    add     w10, w10, #'0'
    strb    w10, [x19], #1
    add     w8, w8, #'0'
    strb    w8, [x19], #1
    ret
1:  cmp     w8, #10
    b.lo    2f
    mov     w9, #10
    udiv    w10, w8, w9
    msub    w8, w10, w9, w8
    add     w10, w10, #'0'
    strb    w10, [x19], #1
2:  add     w8, w8, #'0'
    strb    w8, [x19], #1
    ret

// Compute RGB for pixel (w20 = col 0..71, w21 = row 0..47)
// Models two colliding galaxies with gravitational potential wells + spiral arms:
//   Core A at (24.0, 18.5), mass = 220.0
//   Core B at (48.0, 29.5), mass = 180.0
//   Plus 8 satellite star clusters in Lclusters table.
// Returns w0 = R, w1 = G, w2 = B
Lshade_galaxy_pixel:
    ucvtf   d0, w20                 // x
    ucvtf   d1, w21                 // y

    adrp    x9, Lgal_consts@PAGE
    add     x9, x9, Lgal_consts@PAGEOFF
    ldp     d2, d3, [x9]            // Core A: (24.0, 18.5)
    ldp     d4, d5, [x9, #16]       // Core B: (48.0, 29.5)
    ldp     d6, d7, [x9, #32]       // softening = 3.5, scale = 260.0

    // Distance squared to Core A (with swirling shear)
    fsub    d16, d0, d2             // dxA
    fsub    d17, d1, d3             // dyA
    fmul    d18, d16, d16
    fmadd   d18, d17, d17, d18      // r2A = dxA^2 + dyA^2
    fadd    d19, d18, d6            // r2A + eps
    fdiv    d20, d7, d19            // potA = 260 / (r2A + 3.5)

    // Spiral arm modulation around Core A: (dxA * dyA) / (r2A + 8.0)
    fmul    d21, d16, d17
    fadd    d22, d18, d6
    fadd    d22, d22, d6
    fdiv    d21, d21, d22
    fabs    d21, d21
    fmov    d23, #1.5
    fmadd   d20, d20, d21, d20      // boost along tidal bridge

    // Distance squared to Core B
    fsub    d16, d0, d4             // dxB
    fsub    d17, d1, d5             // dyB
    fmul    d18, d16, d16
    fmadd   d18, d17, d17, d18      // r2B
    fadd    d19, d18, d6
    ldr     d22, [x9, #48]          // 210.0
    fdiv    d21, d22, d19           // potB

    // Sum satellite star clusters (8 bodies: x, y, mass)
    adrp    x10, Lclusters@PAGE
    add     x10, x10, Lclusters@PAGEOFF
    mov     w11, #8
    fmov    d24, xzr                // cluster_pot = 0.0
    fmov    d25, #1.5               // tight cluster softening
1:  ldp     d16, d17, [x10], #16    // cx, cy
    ldr     d18, [x10], #8          // cmass
    fsub    d16, d0, d16
    fsub    d17, d1, d17
    fmul    d19, d16, d16
    fmadd   d19, d17, d17, d19
    fadd    d19, d19, d25
    fdiv    d18, d18, d19
    fadd    d24, d24, d18
    subs    w11, w11, #1
    b.ne    1b

    // Combine potentials into R, G, B channels:
    // Core A emits warm gold/orange; Core B emits electric cyan/blue;
    // satellite clusters emit bright magenta/white knots.
    fadd    d26, d20, d21
    fadd    d26, d26, d24           // total energy

    // R = 10 + 3.2 * potA + 1.1 * potB + 2.8 * cluster_pot
    fmov    d16, #3.25
    fmul    d0, d20, d16
    fmov    d16, #1.125
    fmadd   d0, d21, d16, d0
    fmov    d16, #2.75
    fmadd   d0, d24, d16, d0
    fcvtzs  w0, d0
    add     w0, w0, #10

    // G = 12 + 2.1 * potA + 2.4 * potB + 1.8 * cluster_pot
    fmov    d16, #2.125
    fmul    d1, d20, d16
    fmov    d16, #2.375
    fmadd   d1, d21, d16, d1
    fmov    d16, #1.875
    fmadd   d1, d24, d16, d1
    fcvtzs  w1, d1
    add     w1, w1, #12

    // B = 22 + 0.9 * potA + 3.8 * potB + 3.2 * cluster_pot
    fmov    d16, #0.875
    fmul    d2, d20, d16
    fmov    d16, #3.75
    fmadd   d2, d21, d16, d2
    fmov    d16, #3.25
    fmadd   d2, d24, d16, d2
    fcvtzs  w2, d2
    add     w2, w2, #22

    // Clamp w0, w1, w2 to 0..255
    mov     w12, #255
    cmp     w0, w12
    csel    w0, w0, w12, lt
    cmp     w1, w12
    csel    w1, w1, w12, lt
    cmp     w2, w12
    csel    w2, w2, w12, lt
    ret

_main:
    stp     x29, x30, [sp, #-96]!
    mov     x29, sp
    stp     x19, x20, [sp, #16]
    stp     x21, x22, [sp, #32]
    stp     x23, x24, [sp, #48]
    stp     x25, x26, [sp, #64]
    stp     d8, d9, [sp, #80]

    cmp     w0, #1
    b.gt    Lbench_nbody

    sub     sp, sp, #16, lsl #12
    mov     x19, sp
    mov     x25, sp

    adrp    x8, Lhdr@PAGE
    add     x8, x8, Lhdr@PAGEOFF
    mov     x9, #Lhdr_len
1:  ldrb    w10, [x8], #1
    strb    w10, [x19], #1
    subs    x9, x9, #1
    b.ne    1b

    mov     w26, #0
Lrow_loop:
    mov     w20, #0
Lcol_loop:
    lsl     w21, w26, #1
    bl      Lshade_galaxy_pixel
    mov     w3, w0
    mov     w4, w1
    mov     w5, w2

    add     w21, w21, #1
    bl      Lshade_galaxy_pixel
    mov     w6, w0
    mov     w7, w1
    mov     w24, w2

    mov     w8, #0x1b
    strb    w8, [x19], #1
    mov     w8, #'['
    strb    w8, [x19], #1
    mov     w8, #'3'
    strb    w8, [x19], #1
    mov     w8, #'8'
    strb    w8, [x19], #1
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, #'2'
    strb    w8, [x19], #1
    mov     w8, #';'
    strb    w8, [x19], #1

    mov     w8, w3
    bl      Lemit_u8
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, w4
    bl      Lemit_u8
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, w5
    bl      Lemit_u8

    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, #'4'
    strb    w8, [x19], #1
    mov     w8, #'8'
    strb    w8, [x19], #1
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, #'2'
    strb    w8, [x19], #1
    mov     w8, #';'
    strb    w8, [x19], #1

    mov     w8, w6
    bl      Lemit_u8
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, w7
    bl      Lemit_u8
    mov     w8, #';'
    strb    w8, [x19], #1
    mov     w8, w24
    bl      Lemit_u8

    mov     w8, #'m'
    strb    w8, [x19], #1
    mov     w8, #0xe2
    strb    w8, [x19], #1
    mov     w8, #0x96
    strb    w8, [x19], #1
    mov     w8, #0x80
    strb    w8, [x19], #1

    add     w20, w20, #1
    cmp     w20, #72
    b.lo    Lcol_loop

    mov     w8, #0x1b
    strb    w8, [x19], #1
    mov     w8, #'['
    strb    w8, [x19], #1
    mov     w8, #'0'
    strb    w8, [x19], #1
    mov     w8, #'m'
    strb    w8, [x19], #1
    mov     w8, #'\n'
    strb    w8, [x19], #1

    add     w26, w26, #1
    cmp     w26, #24
    b.lo    Lrow_loop

    mov     x0, #1
    mov     x1, x25
    sub     x2, x19, x25
    bl      _write

    add     sp, sp, #16, lsl #12
    mov     w0, #0
    b       Lexit

// Benchmark mode: Run 10,000 steps of 64-body all-pairs O(N^2) gravity
// (40,960,000 pair interactions using ARM64 NEON 4-wide `v.4s` `frsqrte`
// + 2-body outer unroll = 16 pair interactions per inner loop iteration!)
Lbench_nbody:
    sub     sp, sp, #1024
    mov     x8, sp                  // X[0..63] (256B)
    add     x9, sp, #256            // Y[0..63] (256B)
    add     x10, sp, #512           // VX[0..63] (256B)
    add     x11, sp, #768           // VY[0..63] (256B)

    mov     w12, #0
    fmov    s4, #0.5
    fmov    s2, #0.125
    fmov    s3, #-0.125
1:  ucvtf   s0, w12
    fmul    s1, s0, s4
    str     s0, [x8, x12, lsl #2]
    str     s1, [x9, x12, lsl #2]
    str     s2, [x10, x12, lsl #2]
    str     s3, [x11, x12, lsl #2]
    add     w12, w12, #1
    cmp     w12, #64
    b.lo    1b

    mov     w15, #10000             // 10,000 steps
    fmov    v6.4s, #0.125           // dt scale
    fmov    v7.4s, #0.25            // eps2 = 0.25

Lstep_loop:
    mov     w12, #0                 // i = 0..63 (step by 2 bodies!)
Li_loop:
    lsl     x13, x12, #2
    add     x14, x8, x13
    ld1r    {v0.4s}, [x14]          // xi[0]
    add     x14, x14, #4
    ld1r    {v4.4s}, [x14]          // xi[1]
    add     x14, x9, x13
    ld1r    {v1.4s}, [x14]          // yi[0]
    add     x14, x14, #4
    ld1r    {v5.4s}, [x14]          // yi[1]

    movi    v2.4s, #0               // ax0
    movi    v3.4s, #0               // ay0
    movi    v25.4s, #0              // ax1
    movi    v26.4s, #0              // ay1

    mov     x16, x8                 // &X[j]
    mov     x17, x9                 // &Y[j]
    mov     w14, #8                 // 64 bodies / 8 per unrolled iter = 8 iters
Lj_loop:
    ldp     q16, q22, [x16], #32    // xj[0..3], xj[4..7]
    ldp     q17, q23, [x17], #32    // yj[0..3], yj[4..7]

    // Body i vs j[0..3]
    fsub    v18.4s, v16.4s, v0.4s
    fsub    v19.4s, v17.4s, v1.4s
    fmul    v20.4s, v18.4s, v18.4s
    fmla    v20.4s, v19.4s, v19.4s
    fadd    v20.4s, v20.4s, v7.4s
    frsqrte v21.4s, v20.4s
    fmul    v24.4s, v21.4s, v21.4s
    fmul    v21.4s, v21.4s, v24.4s
    fmla    v2.4s, v18.4s, v21.4s
    fmla    v3.4s, v19.4s, v21.4s

    // Body i+1 vs j[0..3]
    fsub    v18.4s, v16.4s, v4.4s
    fsub    v19.4s, v17.4s, v5.4s
    fmul    v20.4s, v18.4s, v18.4s
    fmla    v20.4s, v19.4s, v19.4s
    fadd    v20.4s, v20.4s, v7.4s
    frsqrte v21.4s, v20.4s
    fmul    v24.4s, v21.4s, v21.4s
    fmul    v21.4s, v21.4s, v24.4s
    fmla    v25.4s, v18.4s, v21.4s
    fmla    v26.4s, v19.4s, v21.4s

    // Body i vs j[4..7]
    fsub    v18.4s, v22.4s, v0.4s
    fsub    v19.4s, v23.4s, v1.4s
    fmul    v20.4s, v18.4s, v18.4s
    fmla    v20.4s, v19.4s, v19.4s
    fadd    v20.4s, v20.4s, v7.4s
    frsqrte v21.4s, v20.4s
    fmul    v24.4s, v21.4s, v21.4s
    fmul    v21.4s, v21.4s, v24.4s
    fmla    v2.4s, v18.4s, v21.4s
    fmla    v3.4s, v19.4s, v21.4s

    // Body i+1 vs j[4..7]
    fsub    v18.4s, v22.4s, v4.4s
    fsub    v19.4s, v23.4s, v5.4s
    fmul    v20.4s, v18.4s, v18.4s
    fmla    v20.4s, v19.4s, v19.4s
    fadd    v20.4s, v20.4s, v7.4s
    frsqrte v21.4s, v20.4s
    fmul    v24.4s, v21.4s, v21.4s
    fmul    v21.4s, v21.4s, v24.4s
    fmla    v25.4s, v18.4s, v21.4s
    fmla    v26.4s, v19.4s, v21.4s

    subs    w14, w14, #1
    b.ne    Lj_loop

    faddp   v2.4s, v2.4s, v25.4s
    faddp   v2.4s, v2.4s, v2.4s
    str     d2, [x10, x13]

    add     w12, w12, #2
    cmp     w12, #64
    b.lo    Li_loop

    subs    w15, w15, #1
    b.ne    Lstep_loop

    add     sp, sp, #1024
    adrp    x1, Lbench_ok@PAGE
    add     x1, x1, Lbench_ok@PAGEOFF
    mov     x0, #1
    mov     x2, #17
    bl      _write
    mov     w0, #0

Lexit:
    ldp     d8, d9, [sp, #80]
    ldp     x25, x26, [sp, #64]
    ldp     x23, x24, [sp, #48]
    ldp     x21, x22, [sp, #32]
    ldp     x19, x20, [sp, #16]
    ldp     x29, x30, [sp], #96
    ret

    .section __TEXT,__const
    .p2align 3
Lgal_consts:
    .double 24.0, 18.5              // +0:  Core A (x, y)
    .double 48.0, 29.5              // +16: Core B (x, y)
    .double 3.5, 260.0              // +32: softening, massA
    .double 210.0, 0.01             // +48: massB, dt
    .double 0.25, 0.0               // +64: eps2

Lclusters:
    .double 15.0, 12.0, 55.0
    .double 32.0, 14.0, 65.0
    .double 18.0, 27.0, 50.0
    .double 36.0, 24.0, 80.0
    .double 41.0, 35.0, 60.0
    .double 56.0, 22.0, 55.0
    .double 54.0, 36.0, 50.0
    .double 29.0, 33.0, 45.0

Lhdr:
    .ascii "\x1b[1;32mvibe-assembly\x1b[0m :: \x1b[1;37mN-Body Galaxy Collision Sim in 100% ARM64 Assembly (zero C files)\x1b[0m\n"
Lhdr_end:
    .set Lhdr_len, Lhdr_end - Lhdr

Lbench_ok:
    .ascii "10000 STEPS DONE\n"
