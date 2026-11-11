// Shootout driver, in assembly (arm64, macOS). See shootout/PROTOCOL.md.
//
//     prog <input-file> <min_ms>
//
// No compiler is involved in building the assembly entry: this file, a three-line
// adapter and the verified kernel from solutions/ are assembled and linked. It uses
// libSystem for what every entry needs from the operating system (open, read, malloc,
// the clock, printf) and nothing else.
//
// The adapter (langs/asm/<kernel>.s) provides:
//     _run(data, len, scratch) -> u64      the timed call
//     _digest(scratch, result) -> u64      untimed check of the output, or 0
//
// Register plan (all callee-saved, so they survive the calls):
//     x19 argv, later the result      x20 min_ns        x21 fd, later t0
//     x22 input length                x23 input data    x24 read offset, later scratch
//     x25 best_ns   x26 total_ns      x27 calls         x28 warm-up result

    .text
    .globl  _main
    .p2align 2
_main:
    stp     x29, x30, [sp, #-96]!
    mov     x29, sp
    stp     x19, x20, [sp, #16]
    stp     x21, x22, [sp, #32]
    stp     x23, x24, [sp, #48]
    stp     x25, x26, [sp, #64]
    stp     x27, x28, [sp, #80]
    sub     sp, sp, #32                 // room for printf's variadic arguments

    cmp     w0, #3
    b.ne    usage
    mov     x19, x1

    ldr     x0, [x19, #16]              // min_ns = strtoull(argv[2], NULL, 10) * 1,000,000
    mov     x1, #0
    mov     w2, #10
    bl      _strtoull
    mov     x9, #0x4240
    movk    x9, #0xF, lsl #16           // 1,000,000
    mul     x20, x0, x9

    ldr     x0, [x19, #8]               // fd = open(argv[1], O_RDONLY)
    mov     w1, #0
    bl      _open
    tbnz    w0, #31, io_error
    mov     w21, w0

    mov     w0, w21                     // len = lseek(fd, 0, SEEK_END)
    mov     x1, #0
    mov     w2, #2
    bl      _lseek
    tbnz    x0, #63, io_error
    mov     x22, x0
    mov     w0, w21                     // lseek(fd, 0, SEEK_SET)
    mov     x1, #0
    mov     w2, #0
    bl      _lseek

    cmp     x22, #0                     // data = malloc(len ? len : 1)
    csinc   x0, x22, xzr, ne
    bl      _malloc
    cbz     x0, io_error
    mov     x23, x0

    mov     x24, #0                     // read the whole file
read_more:
    cmp     x24, x22
    b.hs    read_done
    mov     w0, w21
    add     x1, x23, x24
    sub     x2, x22, x24
    bl      _read
    cmp     x0, #0
    b.le    io_error
    add     x24, x24, x0
    b       read_more
read_done:
    mov     w0, w21
    bl      _close

    lsl     x0, x22, #1                 // scratch = malloc(2 * len + 64), for kernels with output
    add     x0, x0, #64
    bl      _malloc
    cbz     x0, io_error
    mov     x24, x0

    mov     x25, #-1                    // best = UINT64_MAX
    mov     x26, #0                     // total
    mov     x27, #0                     // calls
    cbz     x20, timed                  // min_ms == 0: cold mode, no warm-up
    mov     x0, x23
    mov     x1, x22
    mov     x2, x24
    bl      _run
    mov     x28, x0                     // warm-up result

timed:
    mov     w0, #8                      // CLOCK_UPTIME_RAW
    bl      _clock_gettime_nsec_np
    mov     x21, x0
    mov     x0, x23
    mov     x1, x22
    mov     x2, x24
    bl      _run
    mov     x19, x0
    mov     w0, #8
    bl      _clock_gettime_nsec_np
    sub     x9, x0, x21                 // this call's duration
    cmp     x9, x25
    csel    x25, x9, x25, lo
    add     x26, x26, x9
    add     x27, x27, #1
    cbz     x20, report                 // cold mode: exactly one call
    cmp     x19, x28
    b.ne    changed
    cmp     x27, #3                     // at least 3 calls ...
    b.lo    timed
    cmp     x26, x20                    // ... and min_ms of timed work ...
    b.hs    report
    mov     x9, #0x4240
    movk    x9, #0xF, lsl #16
    cmp     x27, x9                     // ... or 1,000,000 calls
    b.lo    timed

report:
    mov     x0, #0                      // cold mode prints 0 for the digest
    cbz     x20, 1f
    mov     x0, x24
    mov     x1, x19
    bl      _digest
1:  str     x19, [sp, #0]               // on Apple arm64, variadic arguments go on the stack
    str     x0,  [sp, #8]
    str     x25, [sp, #16]
    str     x27, [sp, #24]
    adrp    x0, result_fmt@PAGE
    add     x0, x0, result_fmt@PAGEOFF
    bl      _printf
    mov     w0, #0
    b       leave

usage:
    adrp    x0, usage_msg@PAGE
    add     x0, x0, usage_msg@PAGEOFF
    bl      _puts
    mov     w0, #2
    b       leave
io_error:
    adrp    x0, io_msg@PAGE
    add     x0, x0, io_msg@PAGEOFF
    bl      _perror
    mov     w0, #2
    b       leave
changed:
    adrp    x0, changed_msg@PAGE
    add     x0, x0, changed_msg@PAGEOFF
    bl      _puts
    mov     w0, #3
leave:
    add     sp, sp, #32
    ldp     x19, x20, [sp, #16]
    ldp     x21, x22, [sp, #32]
    ldp     x23, x24, [sp, #48]
    ldp     x25, x26, [sp, #64]
    ldp     x27, x28, [sp, #80]
    ldp     x29, x30, [sp], #96
    ret

// uint64_t fnv1a(const uint8_t *buf, size_t len) -- 64-bit FNV-1a, for adapters' _digest
    .globl  _fnv1a
    .p2align 2
_fnv1a:
    mov     x9, #0x2325                 // offset basis 0xcbf29ce484222325
    movk    x9, #0x8422, lsl #16
    movk    x9, #0x9ce4, lsl #32
    movk    x9, #0xcbf2, lsl #48
    mov     x10, #0x01b3                // prime 0x100000001b3
    movk    x10, #0x100, lsl #32
    cbz     x1, 2f
    add     x1, x0, x1
1:  ldrb    w11, [x0], #1
    eor     x9, x9, x11
    mul     x9, x9, x10
    cmp     x0, x1
    b.ne    1b
2:  mov     x0, x9
    ret

    .section __TEXT,__cstring,cstring_literals
result_fmt:
    .asciz  "RESULT %llu %llu %llu %llu\n"
usage_msg:
    .asciz  "usage: prog <input-file> <min_ms>"
io_msg:
    .asciz  "input"
changed_msg:
    .asciz  "result changed between calls"
