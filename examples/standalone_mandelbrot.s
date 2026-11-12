// examples/standalone_mandelbrot.s
//
// A complete standalone macOS (arm64-darwin) application written 100% in ARM64
// assembly—no C source files, no third-party libraries.
//
// It computes an 80x48 Mandelbrot set using IEEE-754 double-precision NEON
// instructions (`fmul`, `fmla`, `fmls`, `fcmp`) with cardioid & period-2 bulb
// rejection, renders it using Unicode half-blocks (▀) and 24-bit ANSI colors
// into a stack buffer, and writes the frame in a single `_write` call.
//
// Build & run:
//   clang examples/standalone_mandelbrot.s -o /tmp/mandelbrot_app && /tmp/mandelbrot_app

    .section __TEXT,__text,regular,pure_instructions
    .globl _main
    .p2align 4

// Compute escape iterations for point (cr = d0, ci = d1), max_iter = w0.
// Returns iteration count in w0.
_mandel_point:
    // Cardioid check: q = (cr - 0.25)^2 + ci^2; if q*(q + (cr - 0.25)) <= 0.25*ci^2 -> max_iter
    fmov    d2, #0.25
    fsub    d3, d0, d2              // d3 = cr - 0.25
    fmul    d4, d1, d1              // d4 = ci^2
    fmadd   d5, d3, d3, d4          // d5 = q = (cr - 0.25)^2 + ci^2
    fadd    d6, d5, d3              // d6 = q + (cr - 0.25)
    fmul    d6, d5, d6              // d6 = q * (q + (cr - 0.25))
    fmul    d7, d2, d4              // d7 = 0.25 * ci^2
    fcmp    d6, d7
    b.le    Lpoint_in_set

    // Period-2 bulb check: (cr + 1.0)^2 + ci^2 <= 0.0625
    fmov    d2, #1.0
    fadd    d3, d0, d2              // d3 = cr + 1.0
    fmadd   d5, d3, d3, d4          // d5 = (cr + 1.0)^2 + ci^2
    fmov    d2, #0.25
    fmul    d2, d2, d2              // d2 = 0.0625
    fcmp    d5, d2
    b.le    Lpoint_in_set

    movi    d2, #0                  // zr = 0.0
    movi    d3, #0                  // zi = 0.0
    fmov    d4, #4.0                // escape threshold 4.0
    mov     w1, #0                  // iter = 0

Lpoint_loop:
    fmul    d5, d2, d2              // zr2 = zr * zr
    fmul    d6, d3, d3              // zi2 = zi * zi
    fadd    d7, d5, d6              // zr2 + zi2
    fcmp    d7, d4
    b.gt    Lpoint_escaped
    add     w1, w1, #1
    cmp     w1, w0
    b.ge    Lpoint_in_set
    fmul    d7, d2, d3              // zr * zi
    fsub    d2, d5, d6
    fadd    d2, d2, d0              // zr = zr2 - zi2 + cr
    fadd    d3, d7, d7
    fadd    d3, d3, d1              // zi = 2*zr*zi + ci
    b       Lpoint_loop

Lpoint_escaped:
    mov     w0, w1
Lpoint_in_set:
    ret

// Append unsigned decimal integer in w0 to buffer at x19 (advances x19).
_put_u32:
    mov     w2, #100
    udiv    w3, w0, w2
    cbz     w3, Lput_tens
    add     w4, w3, #'0'
    strb    w4, [x19], #1
    msub    w0, w3, w2, w0
    mov     w2, #10
    udiv    w3, w0, w2
    add     w4, w3, #'0'
    strb    w4, [x19], #1
    msub    w0, w3, w2, w0
    b       Lput_ones
Lput_tens:
    mov     w2, #10
    udiv    w3, w0, w2
    cbz     w3, Lput_ones
    add     w4, w3, #'0'
    strb    w4, [x19], #1
    msub    w0, w3, w2, w0
Lput_ones:
    add     w0, w0, #'0'
    strb    w0, [x19], #1
    ret

// Map iteration count w0 (0..64) to RGB in w1 (R), w2 (G), w3 (B).
_iter_to_rgb:
    cmp     w0, #64
    b.ge    Lrgb_interior
    // Smooth vivid palette from escape count:
    // R = min(255, iter * 9), G = min(255, iter * 5 + 18), B = min(255, 70 + iter * 11)
    mov     w4, #9
    mul     w1, w0, w4
    cmp     w1, #255
    csel    w1, w1, w4, lt
    mov     w4, #255
    cmp     w1, w4
    csel    w1, w1, w4, lt

    mov     w4, #5
    mul     w2, w0, w4
    add     w2, w2, #18
    mov     w4, #255
    cmp     w2, w4
    csel    w2, w2, w4, lt

    mov     w4, #11
    mul     w3, w0, w4
    add     w3, w3, #70
    mov     w4, #255
    cmp     w3, w4
    csel    w3, w3, w4, lt
    ret
Lrgb_interior:
    mov     w1, #12
    mov     w2, #15
    mov     w3, #24
    ret

_main:
    stp     x29, x30, [sp, #-64]!
    mov     x29, sp
    stp     x19, x20, [sp, #16]
    stp     x21, x22, [sp, #32]
    stp     x23, x24, [sp, #48]

    // Allocate 64 KiB output buffer on the stack
    sub     sp, sp, #16, lsl #12    // 65,536 bytes
    mov     x19, sp                 // x19 = write cursor

    // Copy header banner
    adrp    x0, Lheader@PAGE
    add     x0, x0, Lheader@PAGEOFF
1:  ldrb    w1, [x0], #1
    cbz     w1, 2f
    strb    w1, [x19], #1
    b       1b
2:
    mov     w20, #0                 // y = 0..47 (2 rows per character line = 24 lines)
Lrow_loop:
    // Left margin "  "
    mov     w0, #' '
    strb    w0, [x19], #1
    strb    w0, [x19], #1

    mov     w21, #0                 // x = 0..71
Lcol_loop:
    // Compute cr = -2.05 + x * (2.65 / 72.0)
    ucvtf   d0, w21
    adrp    x8, Lconsts@PAGE
    add     x8, x8, Lconsts@PAGEOFF
    ldr     d1, [x8, #0]            // step_x = 0.036805555555555557
    ldr     d2, [x8, #8]            // min_x  = -2.05
    fmadd   d0, d0, d1, d2          // d0 = cr
    fmov    x22, d0                 // save cr in x22

    // Top half-pixel: y_top = w20
    ucvtf   d1, w20
    ldr     d2, [x8, #16]           // step_y = 0.05
    ldr     d3, [x8, #24]           // min_y  = -1.175
    fmadd   d1, d1, d2, d3          // d1 = ci_top
    mov     w0, #64
    bl      _mandel_point
    mov     w23, w0                 // w23 = top iter

    // Bottom half-pixel: y_bot = w20 + 1
    add     w0, w20, #1
    ucvtf   d1, w0
    adrp    x8, Lconsts@PAGE
    add     x8, x8, Lconsts@PAGEOFF
    ldr     d2, [x8, #16]
    ldr     d3, [x8, #24]
    fmadd   d1, d1, d2, d3          // d1 = ci_bot
    fmov    d0, x22                 // restore cr
    mov     w0, #64
    bl      _mandel_point
    mov     w24, w0                 // w24 = bot iter

    // Emit "\x1b[38;2;R;G;B;48;2;R;G;Bm▀"
    mov     w0, #0x1b
    strb    w0, [x19], #1
    mov     w0, #'['
    strb    w0, [x19], #1
    mov     w0, #'3'
    strb    w0, [x19], #1
    mov     w0, #'8'
    strb    w0, [x19], #1
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, #'2'
    strb    w0, [x19], #1
    mov     w0, #';'
    strb    w0, [x19], #1

    mov     w0, w23
    bl      _iter_to_rgb
    mov     w23, w2
    mov     w8, w3
    mov     w0, w1
    bl      _put_u32
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, w23
    bl      _put_u32
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, w8
    bl      _put_u32

    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, #'4'
    strb    w0, [x19], #1
    mov     w0, #'8'
    strb    w0, [x19], #1
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, #'2'
    strb    w0, [x19], #1
    mov     w0, #';'
    strb    w0, [x19], #1

    mov     w0, w24
    bl      _iter_to_rgb
    mov     w23, w2
    mov     w8, w3
    mov     w0, w1
    bl      _put_u32
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, w23
    bl      _put_u32
    mov     w0, #';'
    strb    w0, [x19], #1
    mov     w0, w8
    bl      _put_u32
    mov     w0, #'m'
    strb    w0, [x19], #1

    // UTF-8 for '▀' (U+2580): 0xE2 0x96 0x80
    mov     w0, #0xe2
    strb    w0, [x19], #1
    mov     w0, #0x96
    strb    w0, [x19], #1
    mov     w0, #0x80
    strb    w0, [x19], #1

    add     w21, w21, #1
    cmp     w21, #72
    b.lt    Lcol_loop

    // Reset color + newline: "\x1b[0m\n"
    mov     w0, #0x1b
    strb    w0, [x19], #1
    mov     w0, #'['
    strb    w0, [x19], #1
    mov     w0, #'0'
    strb    w0, [x19], #1
    mov     w0, #'m'
    strb    w0, [x19], #1
    mov     w0, #'\n'
    strb    w0, [x19], #1

    add     w20, w20, #2
    cmp     w20, #48
    b.lt    Lrow_loop

    // Copy footer banner
    adrp    x0, Lfooter@PAGE
    add     x0, x0, Lfooter@PAGEOFF
3:  ldrb    w1, [x0], #1
    cbz     w1, 4f
    strb    w1, [x19], #1
    b       3b
4:
    // Write entire buffer to stdout (fd = 1)
    mov     x0, #1
    mov     x1, sp
    sub     x2, x19, x1
    bl      _write

    add     sp, sp, #16, lsl #12
    ldp     x19, x20, [sp, #16]
    ldp     x21, x22, [sp, #32]
    ldp     x23, x24, [sp, #48]
    ldp     x29, x30, [sp], #64
    mov     w0, #0
    ret

    .section __TEXT,__const
    .p2align 3
Lconsts:
    .double 0.036805555555555557    // 2.65 / 72.0
    .double -2.05                   // min_x
    .double 0.05                    // 2.40 / 48.0
    .double -1.175                  // min_y

Lheader:
    .asciz "\n  \x1b[1;32mvibe-assembly\x1b[0m :: standalone ARM64 assembly Mandelbrot renderer (zero C files)\n\n"
Lfooter:
    .asciz "\n  \x1b[2m72x48 IEEE-754 double grid · cardioid & period-2 bulb skip · pure arm64-darwin .s\x1b[0m\n\n"
