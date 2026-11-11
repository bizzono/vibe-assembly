// CORRECT: plain scalar loop. Must pass every gate.
    .text
    .globl _wordcount
    .p2align 2
_wordcount:
    mov     x2, #0
    mov     w3, #0
    cbz     x1, done
    add     x1, x0, x1
loop:
    ldrb    w4, [x0], #1
    cmp     w4, #32
    sub     w5, w4, #9
    ccmp    w5, #4, #0, ne
    b.hi    nonspace
    mov     w3, #0
    b       next
nonspace:
    cbnz    w3, next
    mov     w3, #1
    add     x2, x2, #1
next:
    cmp     x0, x1
    b.ne    loop
done:
    mov     x0, x2
    ret
