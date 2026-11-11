// mandelbrot adapter: the shootout protocol on top of the verified kernel.
    .text
    .globl  _run
    .p2align 2
_run:                               // data = width, height, max_iter as little-endian u32
    ldp     w9, w10, [x0]
    ldr     w2, [x0, #8]
    mov     x0, x9
    mov     x1, x10
    b       _mandelbrot

    .globl  _digest
    .p2align 2
_digest:
    mov     x0, #0
    ret
