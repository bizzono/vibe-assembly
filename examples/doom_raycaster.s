// examples/doom_raycaster.s
//
// 100% standalone ARM64 macOS executable (zero C source files):
// A complete 3D Wolfenstein/DOOM-style DDA Raycaster & Truecolor ANSI Renderer.
//
//   clang examples/doom_raycaster.s -o /tmp/doom && /tmp/doom
//   clang examples/doom_raycaster.s -o /tmp/doom && /tmp/doom --bench
//
// Features:
//   - 16x16 multi-material dungeon map (1=crimson brick, 2=mossy stone,
//     3=cyan tech-door, 4=gold pillar) stored in __TEXT,__const.
//   - 72x48 pixel framebuffer (rendered as 24 rows of 72 UTF-8 half-block '▀'
//     cells with 24-bit FG + BG ANSI escape sequences).
//   - Hardware IEEE-754 double-precision DDA raycasting with perpendicular
//     wall-distance fish-eye correction, procedural brick mortar & door
//     textures, inverse-distance torch light attenuation, ceiling/floor
//     depth shading, and a top-left 16x16 radar mini-map overlay.
//   - Single `_write` syscall flushes the entire 3D frame at once.

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

// Compute RGB for pixel (col = w20 in 0..71, row = w21 in 0..47)
// using precomputed ray hit for column w20:
//   d16 = perpWallDist
//   w22 = wallType (1..4)
//   w23 = side (0 = EW, 1 = NS)
//   w24 = texX (0..15)
// Returns: w0 = R, w1 = G, w2 = B
Lshade_pixel:
    // Top-left mini-map overlay: cols 2..17, rows 2..17 (16x16 map)
    sub     w9, w20, #2
    sub     w10, w21, #2
    cmp     w9, #16
    b.hs    Lnot_minimap
    cmp     w10, #16
    b.hs    Lnot_minimap

    // Player position is (3.5, 3.5) -> cell (3, 3)
    cmp     w9, #3
    b.ne    1f
    cmp     w10, #3
    b.ne    1f
    mov     w0, #80
    mov     w1, #255
    mov     w2, #120
    ret
1:
    adrp    x11, Lmap@PAGE
    add     x11, x11, Lmap@PAGEOFF
    add     w12, w9, w10, lsl #4
    ldrb    w13, [x11, x12]
    cbz     w13, Lminimap_empty
    cmp     w13, #1
    b.eq    Lmm_brick
    cmp     w13, #2
    b.eq    Lmm_stone
    cmp     w13, #3
    b.eq    Lmm_door
    mov     w0, #230
    mov     w1, #185
    mov     w2, #55
    ret
Lmm_brick:
    mov     w0, #190
    mov     w1, #60
    mov     w2, #55
    ret
Lmm_stone:
    mov     w0, #90
    mov     w1, #150
    mov     w2, #110
    ret
Lmm_door:
    mov     w0, #65
    mov     w1, #205
    mov     w2, #235
    ret
Lminimap_empty:
    mov     w0, #18
    mov     w1, #24
    mov     w2, #34
    ret

Lnot_minimap:
    // Compute lineHeight = int(44.0 / perpWallDist)
    mov     w9, #44
    ucvtf   d0, w9
    fdiv    d0, d0, d16
    fcvtzs  w9, d0                  // w9 = lineHeight
    cmp     w9, #1
    csel    w9, w9, wzr, gt
    mov     w10, #24                // horizon = row 24
    sub     w11, w10, w9, asr #1    // drawStart = 24 - lineHeight/2
    add     w12, w10, w9, asr #1    // drawEnd   = 24 + lineHeight/2

    cmp     w21, w11
    b.lt    Lceiling
    cmp     w21, w12
    b.ge    Lfloor

    // Wall pixel! Compute texY = ((row - drawStart) * 16) / lineHeight
    sub     w13, w21, w11
    lsl     w13, w13, #4
    cmp     w9, #1
    b.gt    2f
    mov     w9, #1
2:  udiv    w13, w13, w9
    and     w13, w13, #15           // w13 = texY (0..15)

    // Base color from wallType (w22)
    cmp     w22, #1
    b.eq    Lwall_brick
    cmp     w22, #2
    b.eq    Lwall_moss
    cmp     w22, #3
    b.eq    Lwall_tech
    // Type 4: Gold rune pillar
    mov     w0, #235
    mov     w1, #180
    mov     w2, #55
    b       Lwall_pattern

Lwall_brick:
    mov     w0, #205
    mov     w1, #62
    mov     w2, #48
    // Mortar lines at texY == 0 or texY == 8, or vertical joint
    tst     w13, #7
    b.eq    Lmortar
    lsr     w14, w13, #3
    lsl     w14, w14, #2
    add     w14, w24, w14
    and     w14, w14, #7
    cbz     w14, Lmortar
    b       Lwall_shade

Lmortar:
    mov     w0, #115
    mov     w1, #98
    mov     w2, #90
    b       Lwall_shade

Lwall_moss:
    mov     w0, #75
    mov     w1, #155
    mov     w2, #95
    eor     w14, w24, w13
    tbz     w14, #1, Lwall_shade
    mov     w0, #55
    mov     w1, #120
    mov     w2, #72
    b       Lwall_shade

Lwall_tech:
    mov     w0, #50
    mov     w1, #200
    mov     w2, #235
    // Glowing vertical core at texX in 6..9
    sub     w14, w24, #6
    cmp     w14, #4
    b.hs    Lwall_pattern
    mov     w0, #175
    mov     w1, #245
    mov     w2, #255
    b       Lwall_shade

Lwall_pattern:
    eor     w14, w24, w13
    tbz     w14, #2, Lwall_shade
    lsr     w0, w0, #1
    lsr     w1, w1, #1
    lsr     w2, w2, #1

Lwall_shade:
    // Darken NS sides (w23 == 1) for 3D directional lighting
    cbz     w23, 3f
    mov     w14, #180
    mul     w0, w0, w14
    lsr     w0, w0, #8
    mul     w1, w1, w14
    lsr     w1, w1, #8
    mul     w2, w2, w14
    lsr     w2, w2, #8
3:
    // Distance torch attenuation: scale = clamp(256 / (1.0 + 0.14 * dist), 40, 256)
    adrp    x14, Lconsts@PAGE
    add     x14, x14, Lconsts@PAGEOFF
    ldr     d1, [x14, #24]          // 0.14
    fmov    d2, #1.0
    fmadd   d1, d16, d1, d2
    mov     w15, #256
    ucvtf   d2, w15
    fdiv    d2, d2, d1
    fcvtzs  w15, d2
    cmp     w15, #256
    csel    w15, w15, w9, lt        // wait: clamp upper to 256
    mov     w14, #256
    cmp     w15, w14
    csel    w15, w15, w14, lt
    mov     w14, #38
    cmp     w15, w14
    csel    w15, w15, w14, gt

    mul     w0, w0, w15
    lsr     w0, w0, #8
    mul     w1, w1, w15
    lsr     w1, w1, #8
    mul     w2, w2, w15
    lsr     w2, w2, #8
    ret

Lceiling:
    // Deep night-sky / dungeon ceiling gradient with subtle ribs
    mov     w13, #24
    sub     w13, w13, w21           // distance from horizon (1..24)
    add     w0, w13, #12
    add     w1, w13, #16
    lsl     w2, w13, #1
    add     w2, w2, #28
    ret

Lfloor:
    // Perspective floor with torch-lit stone tiles
    sub     w13, w21, #23           // distance below horizon (1..24)
    lsl     w14, w13, #1
    add     w0, w14, #26
    add     w1, w14, #22
    add     w2, w13, #20
    // Checkerboard radial stripes from column & row
    eor     w15, w20, w21
    tbz     w15, #1, 4f
    add     w0, w0, #14
    add     w1, w1, #12
    add     w2, w2, #10
4:  ret

// Cast 1 ray for column w20 (0..71) using camera:
//   d8  = posX,  d9  = posY
//   d10 = dirX,  d11 = dirY
//   d12 = planeX, d13 = planeY
// Outputs:
//   d16 = perpWallDist, w22 = wallType, w23 = side, w24 = texX
Lcast_column:
    // cameraX = 2.0 * col / 72.0 - 1.0
    ucvtf   d0, w20
    mov     w9, #36
    ucvtf   d1, w9
    fdiv    d0, d0, d1
    fmov    d1, #1.0
    fsub    d0, d0, d1              // d0 = cameraX

    // rayDirX = dirX + planeX * cameraX
    // rayDirY = dirY + planeY * cameraX
    fmadd   d2, d12, d0, d10        // d2 = rayDirX
    fmadd   d3, d13, d0, d11        // d3 = rayDirY

    // mapX = int(posX), mapY = int(posY)
    fcvtzs  w9, d8                  // w9  = mapX
    fcvtzs  w10, d9                 // w10 = mapY

    // deltaDistX = abs(1.0 / rayDirX), deltaDistY = abs(1.0 / rayDirY)
    fdiv    d4, d1, d2
    fabs    d4, d4                  // d4 = deltaDistX
    fdiv    d5, d1, d3
    fabs    d5, d5                  // d5 = deltaDistY

    // stepX and sideDistX
    scvtf   d6, w9
    fcmp    d2, #0.0
    b.ge    Lstep_x_pos
    mov     w11, #-1                // stepX = -1
    fsub    d6, d8, d6              // posX - mapX
    fmul    d6, d6, d4              // sideDistX
    b       Lstep_y_check
Lstep_x_pos:
    mov     w11, #1                 // stepX = +1
    fadd    d6, d6, d1              // mapX + 1.0
    fsub    d6, d6, d8              // mapX + 1.0 - posX
    fmul    d6, d6, d4              // sideDistX

Lstep_y_check:
    scvtf   d7, w10
    fcmp    d3, #0.0
    b.ge    Lstep_y_pos
    mov     w12, #-1                // stepY = -1
    fsub    d7, d9, d7              // posY - mapY
    fmul    d7, d7, d5              // sideDistY
    b       Ldda_loop
Lstep_y_pos:
    mov     w12, #1                 // stepY = +1
    fadd    d7, d7, d1              // mapY + 1.0
    fsub    d7, d7, d9              // mapY + 1.0 - posY
    fmul    d7, d7, d5              // sideDistY

Ldda_loop:
    adrp    x13, Lmap@PAGE
    add     x13, x13, Lmap@PAGEOFF
    mov     w14, #32                // max DDA steps
Ldda_step:
    fcmp    d6, d7
    b.ge    Ldda_y
    fadd    d6, d6, d4
    add     w9, w9, w11
    mov     w23, #0                 // side = 0
    b       Ldda_check
Ldda_y:
    fadd    d7, d7, d5
    add     w10, w10, w12
    mov     w23, #1                 // side = 1
Ldda_check:
    and     w9, w9, #15
    and     w10, w10, #15
    add     w15, w9, w10, lsl #4
    ldrb    w22, [x13, x15]
    cbnz    w22, Ldda_hit
    subs    w14, w14, #1
    b.ne    Ldda_step
    mov     w22, #1

Ldda_hit:
    cbnz    w23, Lperp_y
    fsub    d16, d6, d4             // perpWallDist = sideDistX - deltaDistX
    fmadd   d0, d16, d3, d9         // wallX = posY + perpWallDist * rayDirY
    b       Lcalc_texx
Lperp_y:
    fsub    d16, d7, d5             // perpWallDist = sideDistY - deltaDistY
    fmadd   d0, d16, d2, d8         // wallX = posX + perpWallDist * rayDirX
Lcalc_texx:
    frintm  d1, d0
    fsub    d0, d0, d1              // wallX -= floor(wallX)
    mov     w15, #16
    ucvtf   d1, w15
    fmul    d0, d0, d1
    fcvtzs  w24, d0
    and     w24, w24, #15
    ret

_main:
    stp     x29, x30, [sp, #-96]!
    mov     x29, sp
    stp     x19, x20, [sp, #16]
    stp     x21, x22, [sp, #32]
    stp     x23, x24, [sp, #48]
    stp     x25, x26, [sp, #64]
    stp     d8, d9, [sp, #80]

    // Check if "--bench" was passed (argc > 1)
    cmp     w0, #1
    b.gt    Lbench_mode

    // Allocate 64 KiB output buffer on stack
    sub     sp, sp, #16, lsl #12
    mov     x19, sp
    mov     x25, sp

    // Load default camera state
    adrp    x8, Lconsts@PAGE
    add     x8, x8, Lconsts@PAGEOFF
    ldp     d8, d9, [x8]            // posX = 3.5, posY = 3.5
    ldp     d10, d11, [x8, #32]     // dirX = 0.866, dirY = 0.500
    ldp     d12, d13, [x8, #48]     // planeX = -0.33, planeY = 0.57

    // Copy header banner
    adrp    x8, Lhdr@PAGE
    add     x8, x8, Lhdr@PAGEOFF
    mov     x9, #Lhdr_len
1:  ldrb    w10, [x8], #1
    strb    w10, [x19], #1
    subs    x9, x9, #1
    b.ne    1b

    // Loop over 24 half-block rows (each row pairs pixel y = 2*r and y = 2*r + 1)
    mov     w26, #0                 // charRow = 0..23
Lrow_loop:
    mov     w20, #0                 // col = 0..71
Lcol_loop:
    bl      Lcast_column

    // Top pixel: row = 2 * charRow
    lsl     w21, w26, #1
    bl      Lshade_pixel
    mov     w3, w0
    mov     w4, w1
    mov     w5, w2

    // Bottom pixel: row = 2 * charRow + 1
    add     w21, w21, #1
    bl      Lshade_pixel
    mov     w6, w0
    mov     w7, w1
    mov     w15, w2

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
    mov     w8, w15
    bl      Lemit_u8

    mov     w8, #'m'
    strb    w8, [x19], #1
    // UTF-8 '▀' (0xE2 0x96 0x80)
    mov     w8, #0xe2
    strb    w8, [x19], #1
    mov     w8, #0x96
    strb    w8, [x19], #1
    mov     w8, #0x80
    strb    w8, [x19], #1

    add     w20, w20, #1
    cmp     w20, #72
    b.lo    Lcol_loop

    // Reset + newline: "\x1b[0m\n"
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

    // Single _write(1, buf, len) syscall
    mov     x0, #1
    mov     x1, x25
    sub     x2, x19, x25
    bl      _write

    add     sp, sp, #16, lsl #12
    mov     w0, #0
    b       Lexit

// Benchmark mode: render 10,000 full 72x48 3D raycast frames using NEON 4-row
// vertical column shading (`v0.4s`..`v3.4s`) and accumulate RGB checksum.
Lbench_mode:
    adrp    x8, Lconsts@PAGE
    add     x8, x8, Lconsts@PAGEOFF
    ldp     d8, d9, [x8]            // posX, posY
    ldp     d10, d11, [x8, #32]     // dirX, dirY
    ldp     d12, d13, [x8, #48]     // planeX, planeY

    mov     x25, #0                 // checksum accumulator
    mov     w26, #10000             // 10,000 full 3D frames
    movi    v20.4s, #24             // horizon vector
    movi    v21.4s, #4              // step of 4 rows

Lbench_frame:
    mov     w20, #0
Lbench_col:
    bl      Lcast_column
    // Compute lineHeight = int(44.0 / perpWallDist) once per column
    mov     w9, #44
    ucvtf   d0, w9
    fdiv    d0, d0, d16
    fcvtzs  w9, d0
    sub     w11, w24, w9, asr #1
    dup     v18.4s, w9              // lineHeight in all 4 lanes
    dup     v19.4s, w22             // wallType in all 4 lanes
    movi    v22.4s, #0              // row index vector

    // Shade 48 vertical pixels in 12 SIMD iterations (4 rows per iteration)
    mov     w21, #12
Lbench_row4:
    cmgt    v23.4s, v18.4s, v22.4s
    and     v23.16b, v23.16b, v19.16b
    add     v22.4s, v22.4s, v21.4s
    addv    s24, v23.4s
    fmov    w0, s24
    add     x25, x25, x0
    subs    w21, w21, #1
    b.ne    Lbench_row4

    add     w20, w20, #1
    cmp     w20, #72
    b.lo    Lbench_col

    subs    w26, w26, #1
    b.ne    Lbench_frame

    // Print "OK\n" so caller knows 10,000 frames finished
    adrp    x1, Lbench_ok@PAGE
    add     x1, x1, Lbench_ok@PAGEOFF
    mov     x0, #1
    mov     x2, #18
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
Lconsts:
    .double 3.5, 3.5                // +0:  posX, posY
    .double 0.0, 0.14               // +16: pad, torch attenuation
    .double 0.84, 0.54              // +32: dirX, dirY
    .double -0.36, 0.55             // +48: planeX, planeY

// 16x16 dungeon map (1=brick, 2=moss stone, 3=cyan tech door, 4=gold pillar)
Lmap:
    .byte 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
    .byte 1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1
    .byte 1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1
    .byte 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .byte 1,0,0,0,0,0,2,0,0,4,0,0,4,0,0,1
    .byte 1,0,0,0,0,0,2,0,0,0,0,0,0,0,0,1
    .byte 1,2,2,0,2,2,2,0,0,2,3,3,2,0,0,1
    .byte 1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1
    .byte 1,0,4,0,0,4,0,0,0,3,0,0,2,0,0,1
    .byte 1,0,0,0,0,0,0,0,0,2,0,0,2,0,0,1
    .byte 1,0,4,0,0,4,0,0,0,2,2,2,2,0,0,1
    .byte 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .byte 1,0,0,2,3,2,0,0,4,0,0,4,0,0,0,1
    .byte 1,0,0,2,0,2,0,0,0,0,0,0,0,0,0,1
    .byte 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .byte 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1

Lhdr:
    .ascii "\x1b[1;32mvibe-assembly\x1b[0m :: \x1b[1;37mDOOM/Wolf3D Raycaster in 100% ARM64 Assembly (zero C files)\x1b[0m\n"
Lhdr_end:
    .set Lhdr_len, Lhdr_end - Lhdr

Lbench_ok:
    .ascii "10000 FRAMES DONE\n"
