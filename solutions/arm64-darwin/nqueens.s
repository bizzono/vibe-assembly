// nqueens -- count the solutions of the n-queens puzzle by backtracking search
// uint64_t nqueens(uint64_t n);
//
// Exhaustive row-by-row bitmask backtracking search, with:
//   - `rem = all ^ cols` (remaining unused columns) instead of separate `all` and `cols`
//   - explicit stack for upper rows (0 .. n-7)
//   - rows n-6 .. n-1 specialized in registers (bottom 6 levels of the tree)
//   - rows n-2 and n-1 evaluated branchlessly via 2x2 bipartite matching

    .text
    .globl  _nqueens
    .p2align 4
_nqueens:
    cmp     x0, #31
    b.hi    Lret_zero
    cmp     x0, #1
    b.ls    Lret_one

    stp     x19, x20, [sp, #-496]!
    stp     x21, x22, [sp, #16]
    stp     x23, x24, [sp, #32]
    stp     x25, x26, [sp, #48]
    stp     x27, x28, [sp, #64]
    stp     x29, x30, [sp, #80]

    mov     w1, #1
    lsl     w1, w1, w0
    sub     w1, w1, #1              // w1 = rem = (1 << n) - 1
    mov     x19, x0                 // x19 = n
    mov     x0, #0                  // x0 = total count

    cmp     x19, #2
    b.eq    Lonly_2
    cmp     x19, #3
    b.eq    Lonly_3
    cmp     x19, #4
    b.eq    Lonly_4
    cmp     x19, #5
    b.eq    Lonly_5
    cmp     x19, #6
    b.eq    Lonly_6

    // n >= 7: rows 0 .. n-7 on explicit stack at sp+96, rows n-6 .. n-1 in registers.
    add     x22, sp, #96            // x22 = stack base (row 0)
    mov     x20, x22                // x20 = current stack slot (row d)
    sub     x21, x19, #7
    add     x21, x22, x21, lsl #4   // x21 = stack slot for row n-7

    mov     w27, w1                 // rem for row 0
    mov     w28, #0                 // dl for row 0
    mov     w29, #0                 // dr for row 0
    mov     w30, w1                 // free for row 0

    .p2align 4
Louter_loop:
    neg     w4, w30
    and     w4, w30, w4             // bit = free & -free
    eor     w30, w30, w4            // free ^= bit
    eor     w1, w27, w4             // child rem
    orr     w2, w28, w4
    orr     w3, w29, w4
    lsl     w2, w2, #1              // child dl
    lsr     w3, w3, #1              // child dr

    cmp     x20, x21
    b.eq    Lcall_n6

    orr     w5, w2, w3
    bics    w5, w1, w5
    b.eq    Louter_next

    stp     w27, w28, [x20]
    stp     w29, w30, [x20, #8]
    add     x20, x20, #16
    mov     w27, w1
    mov     w28, w2
    mov     w29, w3
    mov     w30, w5
    b       Louter_loop

Louter_next:
    cbnz    w30, Louter_loop
Lpop:
    cmp     x20, x22
    b.ls    Ldone
    sub     x20, x20, #16
    ldp     w27, w28, [x20]
    ldp     w29, w30, [x20, #8]
    cbnz    w30, Louter_loop
    b       Lpop

    .p2align 4
Lcall_n6:
    orr     w5, w2, w3
    bics    w5, w1, w5              // free6
    b.eq    Louter_next
    stp     w27, w28, [x20]
    stp     w29, w30, [x20, #8]
    mov     w27, w1                 // rem6
    mov     w28, w2                 // dl6
    mov     w29, w3                 // dr6
    mov     w30, w5                 // free6

    .p2align 4
Ln6_loop:
    neg     w4, w30
    and     w4, w30, w4             // bit6
    eor     w30, w30, w4            // free6 ^= bit6
    eor     w23, w27, w4            // rem5
    orr     w24, w28, w4
    orr     w25, w29, w4
    lsl     w24, w24, #1            // dl5
    lsr     w25, w25, #1            // dr5

    orr     w26, w24, w25
    bics    w26, w23, w26           // free5
    b.eq    Ln6_next

    .p2align 4
Ln5_loop:
    neg     w4, w26
    and     w4, w26, w4             // bit5
    eor     w26, w26, w4            // free5 ^= bit5
    eor     w14, w23, w4            // rem4
    orr     w15, w24, w4
    orr     w16, w25, w4
    lsl     w15, w15, #1            // dl4
    lsr     w16, w16, #1            // dr4

    orr     w17, w15, w16
    bics    w17, w14, w17           // free4
    b.eq    Ln5_next

    .p2align 4
Ln4_loop:
    neg     w4, w17
    and     w4, w17, w4             // bit4
    eor     w17, w17, w4            // free4 ^= bit4
    eor     w1, w14, w4             // rem3
    orr     w2, w15, w4
    orr     w3, w16, w4
    lsl     w2, w2, #1              // dl3
    lsr     w3, w3, #1              // dr3

    orr     w4, w2, w3
    bics    w4, w1, w4              // free3
    b.eq    Ln4_next

    lsl     w13, w2, #1
    orr     w13, w13, w3, lsr #1
    bic     w13, w1, w13            // base2 = rem3 & ~((dl3 << 1) | (dr3 >> 1))
    lsl     w12, w2, #2
    orr     w12, w12, w3, lsr #2
    bic     w12, w1, w12            // base1 = rem3 & ~((dl3 << 2) | (dr3 >> 2))

    .p2align 4
Ln3_loop:
    neg     w5, w4
    and     w5, w4, w5              // bit3 = free3 & -free3
    eor     w4, w4, w5              // free3 ^= bit3
    eor     w6, w1, w5              // rem2 = rem3 ^ bit3 (2 bits)
    orr     w7, w5, w5, lsl #1
    orr     w8, w5, w5, lsl #2
    tst     w6, w6, lsl #1          // eq iff the 2 cols in rem2 are not adjacent
    orr     w7, w7, w5, lsr #1      // bit3 | (bit3 << 1) | (bit3 >> 1)
    orr     w8, w8, w5, lsr #2      // bit3 | (bit3 << 2) | (bit3 >> 2)
    bic     w9, w13, w7             // f2 = valid cols in row n-2
    bic     w10, w12, w8            // f1 = valid cols in row n-1
    ccmp    w9, #0, #4, eq          // ne iff !adj && f2 != 0
    orr     w11, w9, w10            // f2 | f1
    and     w7, w9, w10             // f2 & f1
    ccmp    w10, #0, #4, ne         // ne iff !adj && f2 != 0 && f1 != 0
    ccmp    w11, w6, #0, ne         // eq iff !adj && f2 != 0 && f1 != 0 && (f2 | f1) == rem2
    cinc    x0, x0, eq
    ccmp    w7, w6, #0, eq          // eq iff above && (f2 & f1) == rem2
    cinc    x0, x0, eq
    cbnz    w4, Ln3_loop

Ln4_next:
    cbnz    w17, Ln4_loop
Ln5_next:
    cbnz    w26, Ln5_loop
Ln6_next:
    cbnz    w30, Ln6_loop

    cmp     x19, #6
    b.ls    Ldone
    ldp     w27, w28, [x20]
    ldp     w29, w30, [x20, #8]
    cbnz    w30, Louter_loop
    b       Lpop

Lonly_6:
    mov     w27, w1
    mov     w28, #0
    mov     w29, #0
    mov     w30, w1
    b       Ln6_loop

Lonly_5:
    mov     w23, w1
    mov     w24, #0
    mov     w25, #0
    mov     w26, w1
    mov     w30, #0
    b       Ln5_loop

Lonly_4:
    mov     w14, w1
    mov     w15, #0
    mov     w16, #0
    mov     w17, w1
    mov     w26, #0
    mov     w30, #0
    b       Ln4_loop

Lonly_3:
    mov     w4, w1
    mov     w13, w1
    mov     w12, w1
    mov     w17, #0
    mov     w26, #0
    mov     w30, #0
    b       Ln3_loop

Lonly_2:
    tst     w1, w1, lsl #1
    cset    x0, eq

Ldone:
    ldp     x29, x30, [sp, #80]
    ldp     x27, x28, [sp, #64]
    ldp     x25, x26, [sp, #48]
    ldp     x23, x24, [sp, #32]
    ldp     x21, x22, [sp, #16]
    ldp     x19, x20, [sp], #496
    ret

Lret_zero:
    mov     x0, #0
    ret
Lret_one:
    mov     x0, #1
    ret
