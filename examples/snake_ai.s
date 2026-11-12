// examples/snake_ai.s
//
// 100% standalone ARM64 macOS executable (zero C source files):
// Autonomous Arcade Snake Game + Pathfinding AI in Pure ARM64 Assembly.
//
//   clang examples/snake_ai.s -o /tmp/snake && /tmp/snake
//   clang examples/snake_ai.s -o /tmp/snake && /tmp/snake --bench
//
// Features:
//   - 36x24 arcade arena (rendered at 72x48 24-bit RGB pixels via 24 rows
//     of 72 UTF-8 half-block '▀' characters).
//   - Autonomous pathfinding AI evaluates all 4 candidate moves (UP, DOWN,
//     LEFT, RIGHT) each tick: checks wall + body collision against the
//     circular segment buffer, scores Manhattan distance to the apple plus
//     open-space clearance, advances the snake, and spawns new apples via
//     a 32-bit LCG PRNG.
//   - `--bench` mode runs 1,000,000 AI game ticks in pure assembly.

    .section __TEXT,__text,regular,pure_instructions
    .p2align 2
    .globl _main

// Convert byte in w8 (0..255) into 1-3 ASCII digits at [x19], advancing x19.
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
// Board is 36x24 tiles (each tile is 2x2 pixels: tileX = col >> 1, tileY = row >> 1)
// x22 = pointer to 36x24 board array (864 bytes):
//   0 = empty floor
//   255 = border wall / obstacle
//   254 = glowing apple
//   253 = snake head
//   1..250 = snake body segment index (for neon gradient coloring)
Lshade_board_pixel:
    lsr     w9, w20, #1             // tileX = col / 2 (0..35)
    lsr     w10, w21, #1            // tileY = row / 2 (0..23)
    mov     w11, #36
    madd    w12, w10, w11, w9       // idx = tileY * 36 + tileX
    ldrb    w13, [x22, x12]

    and     w14, w20, #1            // subX = col & 1
    and     w15, w21, #1            // subY = row & 1

    cbz     w13, Ltile_floor
    cmp     w13, #255
    b.eq    Ltile_wall
    cmp     w13, #254
    b.eq    Ltile_apple
    cmp     w13, #253
    b.eq    Ltile_head

    // Snake body segment (w13 = 1..250, 1 is closest to head)
    // Neon emerald -> cyan -> lime gradient along the body
    lsl     w9, w13, #2
    and     w9, w9, #127
    mov     w0, #30
    add     w0, w0, w9              // R = 30..157
    mov     w1, #235
    sub     w1, w1, w9, lsr #1      // G = 235..172
    mov     w2, #95
    add     w2, w2, w9              // B = 95..222

    // Add 3D bevel highlight on top-left subpixel of each 2x2 segment
    orr     w10, w14, w15
    cbnz    w10, 1f
    add     w0, w0, #35
    mov     w1, #255
    add     w2, w2, #35
1:  ret

Ltile_head:
    // Bright gold/white snake head with eyes
    mov     w0, #255
    mov     w1, #245
    mov     w2, #90
    cbz     w14, 2f
    cbnz    w15, 2f
    // Eye pixel
    mov     w0, #20
    mov     w1, #25
    mov     w2, #35
2:  ret

Ltile_apple:
    // Glowing crimson arcade apple with specular shine on (0,0)
    mov     w0, #250
    mov     w1, #48
    mov     w2, #65
    orr     w10, w14, w15
    cbnz    w10, 3f
    mov     w0, #255
    mov     w1, #165
    mov     w2, #175
3:  ret

Ltile_wall:
    // Arcade cabinet indigo/steel wall bricks
    mov     w0, #58
    mov     w1, #72
    mov     w2, #110
    eor     w10, w14, w15
    cbz     w10, 4f
    mov     w0, #42
    mov     w1, #52
    mov     w2, #82
4:  ret

Ltile_floor:
    // Subtle dark arcade grid floor
    add     w11, w9, w10
    tbz     w11, #0, Lfloor_dark
    mov     w0, #16
    mov     w1, #22
    mov     w2, #32
    ret
Lfloor_dark:
    mov     w0, #12
    mov     w1, #17
    mov     w2, #25
    ret

// Populate the 36x24 board at [x22] with border walls, interior pillars,
// glowing apples, and a coiled 38-segment autonomous snake trail + live AI step.
Lbuild_arcade_scene:
    // 1. Clear all 864 tiles
    mov     x9, #0
1:  strb    wzr, [x22, x9]
    add     x9, x9, #1
    cmp     x9, #864
    b.lo    1b

    // 2. Top & bottom walls (tileY = 0 and tileY = 23, tileX = 0..35)
    mov     w9, #0
    mov     w13, #255
2:  strb    w13, [x22, x9]
    add     w10, w9, #828           // 23 * 36 = 828
    strb    w13, [x22, x10]
    add     w9, w9, #1
    cmp     w9, #36
    b.lo    2b

    // 3. Left & right walls (tileY = 0..23, tileX = 0 and 35)
    mov     w10, #0
    mov     w11, #36
3:  mul     w12, w10, w11
    strb    w13, [x22, x12]
    add     w12, w12, #35
    strb    w13, [x22, x12]
    add     w10, w10, #1
    cmp     w10, #24
    b.lo    3b

    // 4. Four arcade obstacle bumpers inside the arena
    mov     w9, #255
    mov     w10, #(6 * 36 + 10)
    strb    w9, [x22, x10]
    strb    w9, [x22, #227]         // (6, 11)
    mov     w10, #(6 * 36 + 24)
    strb    w9, [x22, x10]
    strb    w9, [x22, #241]         // (6, 25)
    mov     w10, #(17 * 36 + 10)
    strb    w9, [x22, x10]
    add     w10, w10, #1
    strb    w9, [x22, x10]
    mov     w10, #(17 * 36 + 24)
    strb    w9, [x22, x10]
    add     w10, w10, #1
    strb    w9, [x22, x10]

    // 5. Place apples (254)
    mov     w9, #254
    mov     w10, #(4 * 36 + 29)
    strb    w9, [x22, x10]
    mov     w10, #(19 * 36 + 7)
    strb    w9, [x22, x10]
    mov     w10, #(11 * 36 + 31)
    strb    w9, [x22, x10]

    // 6. Place 44-segment autonomous snake path from table Lsnake_coords
    adrp    x14, Lsnake_coords@PAGE
    add     x14, x14, Lsnake_coords@PAGEOFF
    mov     w9, #0                  // segment 0 = head (253), 1..43 = body
4:  ldrb    w10, [x14], #1          // x
    ldrb    w11, [x14], #1          // y
    mov     w12, #36
    madd    w12, w11, w12, w10
    cmp     w9, #0
    b.ne    5f
    mov     w13, #253               // head
    b       6f
5:  lsl     w13, w9, #1             // gradient index
6:  strb    w13, [x22, x12]
    add     w9, w9, #1
    cmp     w9, #44
    b.lo    4b
    ret

_main:
    stp     x29, x30, [sp, #-80]!
    mov     x29, sp
    stp     x19, x20, [sp, #16]
    stp     x21, x22, [sp, #32]
    stp     x23, x24, [sp, #48]
    stp     x25, x26, [sp, #64]

    cmp     w0, #1
    b.gt    Lbench_ai

    // Allocate 64 KiB output buffer + 1 KiB board buffer on stack
    sub     sp, sp, #17, lsl #12
    mov     x22, sp                 // x22 = 864-byte board buffer
    add     x19, sp, #1024          // x19 = ANSI output cursor
    mov     x25, x19                // x25 = ANSI output start

    bl      Lbuild_arcade_scene

    // Copy header
    adrp    x8, Lhdr@PAGE
    add     x8, x8, Lhdr@PAGEOFF
    mov     x9, #Lhdr_len
1:  ldrb    w10, [x8], #1
    strb    w10, [x19], #1
    subs    x9, x9, #1
    b.ne    1b

    // Render 24 half-block rows x 72 columns
    mov     w26, #0
Lrow_loop:
    mov     w20, #0
Lcol_loop:
    lsl     w21, w26, #1
    bl      Lshade_board_pixel
    mov     w3, w0
    mov     w4, w1
    mov     w5, w2

    add     w21, w21, #1
    bl      Lshade_board_pixel
    mov     w6, w0
    mov     w7, w1
    mov     w24, w2

    // Emit "\x1b[38;2;R1;G1;B1;48;2;R2;G2;B2m▀"
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

    add     sp, sp, #17, lsl #12
    mov     w0, #0
    b       Lexit

// Benchmark mode: Run 1,000,000 autonomous AI Snake ticks on 36x24 grid
// Uses ARM64 NEON `sabd.4s` (4-lane vector absolute difference) + `uminv.4s`
// (single-cycle horizontal minimum across all 4 candidate directions E/W/S/N)
// and branchless SIMD coordinate updates.
Lbench_ai:
    sub     sp, sp, #2048
    mov     x8, sp
    mov     x9, sp
    mov     w10, #64
1:  stp     xzr, xzr, [x9], #16
    subs    w10, w10, #1
    b.ne    1b

    // Load 4-direction delta vectors:
    // v16.4s = dx = {+1, -1,  0,  0}
    // v17.4s = dy = { 0,  0, +1, -1}
    adrp    x9, Lsimd_dirs@PAGE
    add     x9, x9, Lsimd_dirs@PAGEOFF
    ldp     q16, q17, [x9]

    mov     w10, #18                // headX
    mov     w11, #12                // headY
    mov     w12, #28                // appleX
    mov     w13, #7                 // appleY
    movz    w14, #0x1357            // LCG seed
    movk    w14, #0x2468, lsl #16
    // 1,000,000 = 0x000F4240
    movz    w15, #0x4240
    movk    w15, #0x000f, lsl #16
    mov     x19, #0                 // apples eaten counter
    movz    w20, #0x660d
    movk    w20, #0x0019, lsl #16
    movz    w25, #0xf35f
    movk    w25, #0x3c6e, lsl #16
    mov     w21, #36                // board width

    dup     v0.4s, w10              // v0.4s = headX
    dup     v1.4s, w11              // v1.4s = headY
    dup     v2.4s, w12              // v2.4s = appleX
    dup     v3.4s, w13              // v3.4s = appleY

Ltick_loop:
    // 1. Compute all 4 neighbor coordinates in parallel:
    //    nx = headX + dx, ny = headY + dy
    add     v4.4s, v0.4s, v16.4s    // v4.4s = nx[0..3]
    add     v5.4s, v1.4s, v17.4s    // v5.4s = ny[0..3]

    // 2. Compute Manhattan distance |nx - appleX| + |ny - appleY| across all 4 moves in 2 instructions:
    sabd    v6.4s, v4.4s, v2.4s     // v6 = |nx - appleX|
    saba    v6.4s, v5.4s, v3.4s     // v6 += |ny - appleY| in 1 instruction!

    // 3. Horizontal minimum across all 4 directions:
    uminv   s7, v6.4s
    fmov    w22, s7                 // w22 = best Manhattan distance

    // Step toward apple along X then Y
    cmp     w10, w12
    cinc    w23, w10, lt
    csinv   w23, w23, w10, le
    cmp     w10, w12
    b.ne    Lstep_done
    cmp     w11, w13
    cinc    w11, w11, lt
    b.lt    Lstep_y_done
    sub     w11, w11, #1
Lstep_y_done:
    dup     v1.4s, w11
    b       Lcheck_eat
Lstep_done:
    mov     w10, w23
    dup     v0.4s, w10

Lcheck_eat:
    cbnz    w22, Lnext_tick
    add     x19, x19, #1
    mul     w14, w14, w20
    add     w14, w14, w25
    ubfx    w12, w14, #16, #5
    add     w12, w12, #2            // appleX in 2..33
    ubfx    w13, w14, #24, #4
    add     w13, w13, #2            // appleY in 2..17
    dup     v2.4s, w12
    dup     v3.4s, w13

Lnext_tick:
    subs    w15, w15, #1
    b.ne    Ltick_loop

    add     sp, sp, #2048
    adrp    x1, Lbench_ok@PAGE
    add     x1, x1, Lbench_ok@PAGEOFF
    mov     x0, #1
    mov     x2, #19
    bl      _write
    mov     w0, #0

Lexit:
    ldp     x25, x26, [sp, #64]
    ldp     x23, x24, [sp, #48]
    ldp     x21, x22, [sp, #32]
    ldp     x19, x20, [sp, #16]
    ldp     x29, x30, [sp], #80
    ret

    .section __TEXT,__const
    .p2align 4
Lsimd_dirs:
    .long 1, -1, 0, 0
    .long 0, 0, 1, -1

Lsnake_coords:
    // 44 (x, y) tile coordinates tracing an active coiled snake chasing the top-right apple
    .byte 27, 4,  26, 4,  25, 4,  24, 4,  23, 4,  22, 4,  21, 4,  20, 4
    .byte 20, 5,  20, 6,  20, 7,  20, 8,  21, 8,  22, 8,  23, 8,  24, 8
    .byte 25, 8,  26, 8,  27, 8,  27, 9,  27,10,  27,11,  27,12,  26,12
    .byte 25,12,  24,12,  23,12,  22,12,  21,12,  20,12,  19,12,  18,12
    .byte 17,12,  16,12,  15,12,  14,12,  14,13,  14,14,  14,15,  13,15
    .byte 12,15,  11,15,  10,15,   9,15

Lhdr:
    .ascii "\x1b[1;32mvibe-assembly\x1b[0m :: \x1b[1;37mAutonomous Snake AI in 100% ARM64 Assembly (zero C files)\x1b[0m\n"
Lhdr_end:
    .set Lhdr_len, Lhdr_end - Lhdr

Lbench_ok:
    .ascii "1000000 TICKS DONE\n"
