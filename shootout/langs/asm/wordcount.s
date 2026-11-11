// wordcount adapter: the shootout protocol on top of the verified kernel.
    .text
    .globl  _run
    .p2align 2
_run:                               // run(data, len, scratch)
    b       _wordcount

    .globl  _digest
    .p2align 2
_digest:                            // no output buffer to check
    mov     x0, #0
    ret
