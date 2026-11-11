// base64_encode adapter: the shootout protocol on top of the verified kernel.
    .text
    .globl  _run
    .p2align 2
_run:                               // run(data, len, scratch) == base64_encode(src, len, dst)
    b       _base64_encode

    .globl  _digest
    .p2align 2
_digest:                            // digest(scratch, bytes_written) = FNV-1a of the output
    b       _fnv1a
