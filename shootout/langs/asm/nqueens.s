// nqueens adapter: the shootout protocol on top of the verified kernel.
    .text
    .globl  _run
    .p2align 2
_run:                               // data = n as a little-endian u32
    ldr     w0, [x0]
    b       _nqueens

    .globl  _digest
    .p2align 2
_digest:
    mov     x0, #0
    ret
