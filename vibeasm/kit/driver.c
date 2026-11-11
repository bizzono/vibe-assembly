/* driver.c -- the vibe-assembly test driver.
 *
 * One driver binary is built per task (it links the task's gen.c). Implementations
 * -- the oracle, the compiler baseline and every assembly candidate -- are loaded as
 * shared libraries, so several can be compared in one process.
 *
 *   driver info
 *   driver check --symbol S --oracle O.dylib --cand C.dylib [--seed N] [--random N]
 *                [--small-max N] [--max-size N] [--large-size N] [--timeout SEC] [--dump FILE]
 *   driver bench --symbol S --oracle O.dylib --cand NAME=C.dylib ... --case 'name|size|flavor' ...
 *                (ints shape: --case 'name|a,b,c,d')  [--samples N] [--sample-us N] [--seed N]
 *   driver call  --symbol S --oracle O.dylib --cand C.dylib (--input FILE | --args a,b,c,d)
 *
 * Output is JSON, one object per line, on stdout.
 *
 * Compile with -DVA_SHAPE=1 (bytes_to_u64), 2 (bytes_to_bytes) or 3 (ints_to_u64).
 */
#define _DARWIN_C_SOURCE 1
#define _GNU_SOURCE 1
#include <dlfcn.h>
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <pthread.h>
#include <pthread/qos.h>
#include <sys/ucontext.h>
#endif

#include "va_kit.h"

#ifndef VA_SHAPE
#error "compile with -DVA_SHAPE=1|2|3"
#endif

#define SHAPE_BYTES_U64 1
#define SHAPE_BYTES_BYTES 2
#define SHAPE_INTS_U64 3

#if VA_SHAPE == SHAPE_BYTES_U64
typedef uint64_t (*fn_t)(const uint8_t *, size_t);
#elif VA_SHAPE == SHAPE_BYTES_BYTES
typedef size_t (*fn_t)(const uint8_t *, size_t, uint8_t *);
#else
typedef uint64_t (*fn_t)(uint64_t, uint64_t, uint64_t, uint64_t);
#endif

extern uint64_t va_tramp(void *fn, uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3,
                         uint64_t *violations, uint64_t poison);
uint64_t va_saved_sp; /* written by the trampoline */

enum { PL_END = 0, PL_START = 1, PL_MID = 2 };
static const char *pl_name[] = {"end", "start", "mid"};

/* ---- small utilities ---------------------------------------------------------- */

static void die(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "driver: ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
    exit(2);
}

static inline uint64_t now_ns(void) {
#if defined(__APPLE__)
    return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}

static uint64_t mix64(uint64_t a, uint64_t b) {
    uint64_t x = a ^ (b + 0x9E3779B97F4A7C15ull + (a << 6) + (a >> 2));
    return va_splitmix(&x);
}

/* Hex-encode up to `max` bytes into a static buffer. */
static const char *hex(const uint8_t *p, size_t len, size_t max) {
    static char bufs[4][2 * 512 + 8];
    static int which;
    char *out = bufs[which++ & 3];
    static const char d[] = "0123456789abcdef";
    size_t n = len < max ? len : max;
    if (n > 512) n = 512;
    for (size_t i = 0; i < n; i++) {
        out[2 * i] = d[p[i] >> 4];
        out[2 * i + 1] = d[p[i] & 15];
    }
    out[2 * n] = 0;
    return out;
}

/* ---- guarded memory regions --------------------------------------------------- */

typedef struct {
    uint8_t *base;  /* start of the mapping (front guard page) */
    uint8_t *lo;    /* first usable byte */
    uint8_t *hi;    /* one past the last usable byte (start of the back guard page) */
    size_t total;
} region;

static size_t g_page;

static region region_new(size_t cap) {
    region r;
    size_t usable = ((cap + g_page) / g_page) * g_page + g_page; /* room for PL_MID offsets */
    r.total = usable + 2 * g_page;
    r.base = mmap(NULL, r.total, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (r.base == MAP_FAILED) die("mmap(%zu) failed: %s", r.total, strerror(errno));
    r.lo = r.base + g_page;
    r.hi = r.lo + usable;
    if (mprotect(r.base, g_page, PROT_NONE) || mprotect(r.hi, g_page, PROT_NONE))
        die("mprotect failed: %s", strerror(errno));
    return r;
}

static void region_prot(const region *r, int prot) {
    if (mprotect(r->lo, (size_t)(r->hi - r->lo), prot)) die("mprotect failed: %s", strerror(errno));
}

/* Where to put a `len`-byte buffer: flush against the back guard (any over-read or
 * over-write faults), flush against the front guard (any under-run faults), or at a
 * random offset in the middle (random alignment). */
static uint8_t *region_place(const region *r, size_t len, int placement, uint64_t rnd) {
    size_t usable = (size_t)(r->hi - r->lo);
    if (len > usable) die("internal: buffer of %zu does not fit region of %zu", len, usable);
    if (placement == PL_END) return r->hi - len;
    if (placement == PL_START) return r->lo;
    return r->lo + (size_t)(rnd % (usable - len + 1));
}

/* ---- state the crash handler reports ------------------------------------------ */

static struct {
    const char *mode;
    const char *phase; /* idle | gen | oracle | candidate */
    const char *cand;
    const char *cand_path;
    uint64_t case_index;
    size_t len;
    unsigned flavor;
    int placement;
    uint64_t seed;
    const uint8_t *in_ptr;
    size_t in_len;
    const uint8_t *out_ptr;
    size_t out_cap;
    uint64_t args[4];
    int have_args;
    uint64_t poison;
    const char *dump_path;
} g = {.mode = "?", .phase = "idle", .cand = "", .cand_path = ""};

static void dump_input(void) {
    if (!g.dump_path || !g.in_ptr) return;
    FILE *f = fopen(g.dump_path, "wb");
    if (!f) return;
    fwrite(g.in_ptr, 1, g.in_len, f);
    fclose(f);
}

static int in_range(uintptr_t a, const uint8_t *lo, size_t n) {
    return a >= (uintptr_t)lo && a < (uintptr_t)lo + n;
}

static void describe_fault(uintptr_t addr, char *out, size_t n) {
    out[0] = 0;
    if (g.in_ptr) {
        uintptr_t s = (uintptr_t)g.in_ptr, e = s + g.in_len;
        if (in_range(addr, g.in_ptr, g.in_len)) {
            snprintf(out, n, "write to the read-only INPUT buffer at offset %zu (inputs must not be modified)",
                     (size_t)(addr - s));
            return;
        }
        if (addr >= e && addr < e + g_page) {
            snprintf(out, n, "access %zu byte(s) PAST THE END of the input buffer (len=%zu): over-read",
                     (size_t)(addr - e) + 1, g.in_len);
            return;
        }
        if (addr < s && addr + g_page >= s) {
            snprintf(out, n, "access %zu byte(s) BEFORE THE START of the input buffer: under-read",
                     (size_t)(s - addr));
            return;
        }
    }
    if (g.out_ptr) {
        uintptr_t s = (uintptr_t)g.out_ptr, e = s + g.out_cap;
        if (addr >= e && addr < e + g_page) {
            snprintf(out, n, "access %zu byte(s) PAST THE END of the output buffer (capacity=%zu): overflow",
                     (size_t)(addr - e) + 1, g.out_cap);
            return;
        }
        if (addr < s && addr + g_page >= s) {
            snprintf(out, n, "access %zu byte(s) BEFORE THE START of the output buffer: underflow",
                     (size_t)(s - addr));
            return;
        }
    }
    if (addr < 4096) snprintf(out, n, "null-pointer dereference");
    else snprintf(out, n, "wild address (not near the input or output buffer)");
}

static const char *sig_name(int sig) {
    switch (sig) {
    case SIGSEGV: return "SIGSEGV";
    case SIGBUS: return "SIGBUS";
    case SIGILL: return "SIGILL";
    case SIGFPE: return "SIGFPE";
    case SIGTRAP: return "SIGTRAP";
    case SIGABRT: return "SIGABRT";
    case SIGALRM: return "SIGALRM";
    default: return "SIGNAL";
    }
}

static void on_signal(int sig, siginfo_t *si, void *uctx) {
    static char buf[8192];
    char note[256];
    size_t o = 0;
    uintptr_t fault = (uintptr_t)si->si_addr, pc = 0, sp = 0, lr = 0, fp = 0;
    uint64_t x[31];
    int have_regs = 0;
    memset(x, 0, sizeof x);
#if defined(__APPLE__) && defined(__aarch64__)
    ucontext_t *uc = (ucontext_t *)uctx;
    if (uc && uc->uc_mcontext) {
        pc = (uintptr_t)uc->uc_mcontext->__ss.__pc;
        sp = (uintptr_t)uc->uc_mcontext->__ss.__sp;
        lr = (uintptr_t)uc->uc_mcontext->__ss.__lr;
        fp = (uintptr_t)uc->uc_mcontext->__ss.__fp;
        for (int i = 0; i < 29; i++) x[i] = uc->uc_mcontext->__ss.__x[i];
        x[29] = fp;
        x[30] = lr;
        have_regs = 1;
    }
#else
    (void)uctx;
#endif
    if (sig == SIGALRM) {
        snprintf(note, sizeof note, "timeout: the call did not return (infinite loop?)");
    } else if (sig == SIGILL) {
        snprintf(note, sizeof note, "illegal instruction (bad encoding, or data executed as code)");
    } else if (sig == SIGTRAP) {
        snprintf(note, sizeof note, "trap/breakpoint instruction executed (brk)");
    } else {
        describe_fault(fault, note, sizeof note);
    }

    Dl_info di;
    const char *sym = "";
    const char *image = "";
    uintptr_t sym_off = 0;
    memset(&di, 0, sizeof di);
    if (pc && dladdr((void *)pc, &di)) {
        if (di.dli_sname) { sym = di.dli_sname; sym_off = pc - (uintptr_t)di.dli_saddr; }
        if (di.dli_fname) image = di.dli_fname;
    }
    int in_cand = g.cand_path[0] && image[0] && strcmp(image, g.cand_path) == 0;

    o += (size_t)snprintf(buf + o, sizeof buf - o,
        "{\"ev\":\"crash\",\"mode\":\"%s\",\"cand\":\"%s\",\"phase\":\"%s\",\"signal\":\"%s\","
        "\"note\":\"%s\",\"fault_addr\":\"0x%" PRIxPTR "\",\"pc\":\"0x%" PRIxPTR "\","
        "\"pc_symbol\":\"%s\",\"pc_offset\":%" PRIuPTR ",\"pc_in_candidate\":%s,"
        "\"case\":%" PRIu64 ",\"len\":%zu,\"flavor\":%u,\"flavor_name\":\"%s\",\"placement\":\"%s\",\"seed\":%" PRIu64,
        g.mode, g.cand, g.phase, sig_name(sig), note, fault, pc, sym, sym_off,
        in_cand ? "true" : "false", g.case_index, g.len, g.flavor,
        g.flavor < va_flavors() ? va_flavor_name(g.flavor) : "?", pl_name[g.placement], g.seed);
    if (g.have_args)
        o += (size_t)snprintf(buf + o, sizeof buf - o,
            ",\"args\":[%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "]",
            g.args[0], g.args[1], g.args[2], g.args[3]);
    if (g.in_ptr)
        o += (size_t)snprintf(buf + o, sizeof buf - o,
            ",\"in_ptr\":\"0x%" PRIxPTR "\",\"in_len\":%zu", (uintptr_t)g.in_ptr, g.in_len);
    if (g.out_ptr)
        o += (size_t)snprintf(buf + o, sizeof buf - o,
            ",\"out_ptr\":\"0x%" PRIxPTR "\",\"out_cap\":%zu", (uintptr_t)g.out_ptr, g.out_cap);
    if (have_regs) {
        o += (size_t)snprintf(buf + o, sizeof buf - o,
            ",\"poison\":\"0x%" PRIx64 "\",\"sp\":\"0x%" PRIxPTR "\",\"regs\":[", g.poison, sp);
        for (int i = 0; i < 31; i++)
            o += (size_t)snprintf(buf + o, sizeof buf - o, "%s\"0x%" PRIx64 "\"", i ? "," : "", x[i]);
        o += (size_t)snprintf(buf + o, sizeof buf - o, "]");
    }
    o += (size_t)snprintf(buf + o, sizeof buf - o, "}\n");
    ssize_t w = write(1, buf, o);
    (void)w;
    /* The input buffer may be unreadable only if the generator itself faulted. */
    if (strcmp(g.phase, "gen") != 0) dump_input();
    _exit(70);
}

static void install_handlers(void) {
    static uint8_t altstack[1 << 16];
    stack_t ss = {.ss_sp = altstack, .ss_size = sizeof altstack, .ss_flags = 0};
    sigaltstack(&ss, NULL);
    struct sigaction sa;
    memset(&sa, 0, sizeof sa);
    sa.sa_sigaction = on_signal;
    sa.sa_flags = SA_SIGINFO | SA_ONSTACK;
    sigemptyset(&sa.sa_mask);
    int sigs[] = {SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGTRAP, SIGABRT, SIGALRM};
    for (size_t i = 0; i < sizeof sigs / sizeof sigs[0]; i++) sigaction(sigs[i], &sa, NULL);
}

/* ---- loading implementations -------------------------------------------------- */

static void *load_fn(const char *path, const char *symbol) {
    void *h = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!h) die("dlopen(%s): %s", path, dlerror());
    void *f = dlsym(h, symbol);
    if (!f) die("dlsym(%s) in %s: %s", symbol, path, dlerror());
    return f;
}

static const char *abi_reg_name(int bit) {
    static const char *names[] = {"x19", "x20", "x21", "x22", "x23", "x24", "x25", "x26", "x27", "x28",
                                  "d8",  "d9",  "d10", "d11", "d12", "d13", "d14", "d15"};
    if (bit < 18) return names[bit];
    if (bit == 20) return "sp";
    if (bit == 21) return "x29";
    return "?";
}

static void abi_list(uint64_t viol, char *out, size_t n) {
    size_t o = 0;
    out[0] = 0;
    for (int b = 0; b < 22; b++)
        if (viol & (1ull << b))
            o += (size_t)snprintf(out + o, n - o, "%s\"%s\"", o ? "," : "", abi_reg_name(b));
}

/* ---- one differential test case ----------------------------------------------- */

typedef struct {
    size_t len;
    unsigned flavor;
    int placement;
    uint64_t seed;
} fcase;

typedef struct {
    fn_t oracle, cand;
    region in, out, exp;
    unsigned timeout;
    uint64_t cases;
} ctx_t;

#define POISON(seed) (mix64(seed, 0xABADCAFEull) | 0x8000000000000001ull)

static void emit_fail_head(const char *kind, const fcase *c) {
    dprintf(1,
        "{\"ev\":\"fail\",\"cand\":\"%s\",\"kind\":\"%s\",\"case\":%" PRIu64 ",\"len\":%zu,"
        "\"flavor\":%u,\"flavor_name\":\"%s\",\"placement\":\"%s\",\"seed\":%" PRIu64,
        g.cand, kind, g.case_index, c->len, c->flavor, va_flavor_name(c->flavor),
        pl_name[c->placement], c->seed);
}

#if VA_SHAPE == SHAPE_BYTES_U64 || VA_SHAPE == SHAPE_BYTES_BYTES

/* Returns 0 when the candidate agrees with the oracle and kept the ABI. */
static int run_case(ctx_t *cx, const fcase *c) {
    va_rng r;
    va_seed(&r, c->seed);
    uint64_t rnd = va_next(&r);

    region_prot(&cx->in, PROT_READ | PROT_WRITE);
    uint8_t *p = region_place(&cx->in, c->len, c->placement, rnd);
    g.len = c->len; g.flavor = c->flavor; g.placement = c->placement; g.seed = c->seed;
    g.in_ptr = p; g.in_len = c->len; g.out_ptr = NULL; g.out_cap = 0;
    g.phase = "gen";
    va_gen(&r, p, c->len, c->flavor);
    region_prot(&cx->in, PROT_READ);

    uint64_t viol = 0;
    g.poison = POISON(c->seed);
#if VA_SHAPE == SHAPE_BYTES_U64
    g.phase = "oracle";
    uint64_t want = cx->oracle(p, c->len);
    g.phase = "candidate";
    alarm(cx->timeout);
    uint64_t got = va_tramp((void *)cx->cand, (uint64_t)(uintptr_t)p, c->len,
                            va_next(&r), va_next(&r), &viol, POISON(c->seed));
    alarm(0);
    g.phase = "idle";
    if (got != want) {
        emit_fail_head("mismatch", c);
        dprintf(1, ",\"expected\":\"%" PRIu64 "\",\"got\":\"%" PRIu64 "\",\"input_hex\":\"%s\",\"input_truncated\":%s}\n",
                want, got, hex(p, c->len, 256), c->len > 256 ? "true" : "false");
        dump_input();
        return 1;
    }
#else
    size_t cap = va_out_cap(c->len);
    /* oracle writes into its own guarded buffer */
    uint8_t *eo = region_place(&cx->exp, cap, PL_END, 0);
    g.phase = "oracle";
    g.out_ptr = eo; g.out_cap = cap;
    size_t want = cx->oracle(p, c->len, eo);
    if (want > cap) die("task bug: reference wrote %zu bytes but va_out_cap(%zu) = %zu", want, c->len, cap);

    uint8_t *dst = region_place(&cx->out, cap, c->placement, va_next(&r));
    memset(cx->out.lo, 0xA5, (size_t)(cx->out.hi - cx->out.lo));
    g.out_ptr = dst; g.out_cap = cap;
    g.phase = "candidate";
    alarm(cx->timeout);
    size_t got = (size_t)va_tramp((void *)cx->cand, (uint64_t)(uintptr_t)p, c->len,
                                  (uint64_t)(uintptr_t)dst, va_next(&r), &viol, POISON(c->seed));
    alarm(0);
    g.phase = "idle";
    if (got != want) {
        emit_fail_head("mismatch", c);
        dprintf(1, ",\"what\":\"return value (bytes written)\",\"expected\":\"%zu\",\"got\":\"%zu\","
                   "\"input_hex\":\"%s\",\"input_truncated\":%s}\n",
                want, got, hex(p, c->len, 256), c->len > 256 ? "true" : "false");
        dump_input();
        return 1;
    }
    if (memcmp(dst, eo, want) != 0) {
        size_t i = 0;
        while (dst[i] == eo[i]) i++;
        size_t from = i > 8 ? i - 8 : 0;
        size_t n = want - from < 32 ? want - from : 32;
        emit_fail_head("mismatch", c);
        dprintf(1, ",\"what\":\"output bytes\",\"first_diff_at\":%zu,\"window_from\":%zu,"
                   "\"expected\":\"%s\",\"got\":\"%s\",\"out_len\":%zu,\"input_hex\":\"%s\",\"input_truncated\":%s}\n",
                i, from, hex(eo + from, n, 32), hex(dst + from, n, 32), want,
                hex(p, c->len, 256), c->len > 256 ? "true" : "false");
        dump_input();
        return 1;
    }
    /* nothing outside [dst, dst+cap) may have been written */
    for (uint8_t *q = cx->out.lo; q < cx->out.hi; q++) {
        if (q == dst) { q += cap; if (q >= cx->out.hi) break; }
        if (*q != 0xA5) {
            emit_fail_head("write_out_of_bounds", c);
            dprintf(1, ",\"offset_from_dst\":%td,\"out_cap\":%zu,\"input_hex\":\"%s\",\"input_truncated\":%s}\n",
                    q - dst, cap, hex(p, c->len, 256), c->len > 256 ? "true" : "false");
            dump_input();
            return 1;
        }
    }
#endif
    if (viol) {
        char regs[256];
        abi_list(viol, regs, sizeof regs);
        emit_fail_head("abi", c);
        dprintf(1, ",\"clobbered\":[%s],\"input_hex\":\"%s\",\"input_truncated\":%s}\n", regs,
                hex(p, c->len, 256), c->len > 256 ? "true" : "false");
        dump_input();
        return 1;
    }
    cx->cases++;
    return 0;
}

static uint64_t log_uniform(va_rng *r, uint64_t max) {
    if (max == 0) return 0;
    int bits = 0;
    while ((max >> bits) > 1) bits++;
    uint64_t hi = 1ull << va_range(r, 0, (uint64_t)bits);
    uint64_t v = va_below(r, hi * 2);
    return v > max ? max : v;
}

static int fuzz(ctx_t *cx, uint64_t seed0, size_t small_max, size_t max_size, size_t large_size,
                uint64_t random_n) {
    unsigned F = va_flavors();
    fcase c;
    g.case_index = 0;
#define RUN() do { c.seed = mix64(seed0, g.case_index); if (run_case(cx, &c)) return 1; g.case_index++; } while (0)

    /* A: every small length, every flavor, flush against both guards */
    for (size_t len = 0; len <= small_max; len++)
        for (unsigned f = 0; f < F; f++)
            for (int pl = PL_END; pl <= PL_START; pl++) {
                c.len = len; c.flavor = f; c.placement = pl;
                RUN();
            }

    /* B: boundary lengths (vector-width and power-of-two edges) */
    for (size_t m = 16; m <= max_size; m = m < 1024 ? m + 16 : m * 2)
        for (int d = -1; d <= 1; d++) {
            size_t len = m + (size_t)d;
            if (len <= small_max || len > max_size) continue;
            for (unsigned f = 0; f < F; f++) {
                c.len = len; c.flavor = f; c.placement = PL_END;
                RUN();
            }
        }

    /* C: random lengths, flavors, placements and alignments */
    va_rng r;
    va_seed(&r, mix64(seed0, 0xC0FFEE));
    for (uint64_t i = 0; i < random_n; i++) {
        c.len = (size_t)log_uniform(&r, max_size);
        c.flavor = (unsigned)va_below(&r, F);
        c.placement = (int)va_below(&r, 3);
        RUN();
    }

    /* D: large inputs (long loops, counter overflow) */
    if (large_size > max_size)
        for (unsigned f = 0; f < F; f++)
            for (int pl = PL_END; pl <= PL_START; pl++) {
                c.len = large_size - (size_t)va_below(&r, 67);
                c.flavor = f; c.placement = pl;
                RUN();
            }
#undef RUN
    return 0;
}

#else /* SHAPE_INTS_U64 */

static int run_case(ctx_t *cx, const fcase *c) {
    va_rng r;
    va_seed(&r, c->seed);
    uint64_t a[4] = {0, 0, 0, 0};
    g.flavor = c->flavor; g.seed = c->seed; g.len = 0; g.placement = 0;
    g.phase = "gen";
    va_gen_args(&r, a, c->flavor);
    memcpy(g.args, a, sizeof a);
    g.have_args = 1;
    g.phase = "oracle";
    uint64_t want = cx->oracle(a[0], a[1], a[2], a[3]);
    uint64_t viol = 0;
    g.poison = POISON(c->seed);
    g.phase = "candidate";
    alarm(cx->timeout);
    uint64_t got = va_tramp((void *)cx->cand, a[0], a[1], a[2], a[3], &viol, POISON(c->seed));
    alarm(0);
    g.phase = "idle";
    if (got != want) {
        emit_fail_head("mismatch", c);
        dprintf(1, ",\"args\":[%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "],\"expected\":\"%" PRIu64 "\",\"got\":\"%" PRIu64 "\"}\n",
                a[0], a[1], a[2], a[3], want, got);
        return 1;
    }
    if (viol) {
        char regs[256];
        abi_list(viol, regs, sizeof regs);
        emit_fail_head("abi", c);
        dprintf(1, ",\"args\":[%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%" PRIu64 "],\"clobbered\":[%s]}\n",
                a[0], a[1], a[2], a[3], regs);
        return 1;
    }
    cx->cases++;
    return 0;
}

static int fuzz(ctx_t *cx, uint64_t seed0, size_t small_max, size_t max_size, size_t large_size,
                uint64_t random_n) {
    (void)small_max; (void)max_size; (void)large_size;
    unsigned F = va_flavors();
    fcase c = {0, 0, 0, 0};
    g.case_index = 0;
    for (uint64_t i = 0; i < random_n; i++) {
        c.flavor = (unsigned)(i % F);
        c.seed = mix64(seed0, g.case_index);
        if (run_case(cx, &c)) return 1;
        g.case_index++;
    }
    return 0;
}

#endif

/* ---- benchmark ---------------------------------------------------------------- */

#define MAX_CANDS 8
#define MAX_CASES 32
#define MAX_SAMPLES 512

typedef struct {
    const char *name;
    const char *path;
    fn_t fn;
} cand_t;

static int cmp_double(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return x < y ? -1 : x > y;
}

static volatile uint64_t g_sink;

typedef struct {
    char name[64];
    size_t size;
    unsigned flavor;
    uint64_t args[4];
} bcase;

static void parse_case(const char *spec, bcase *bc) {
    /* 'name|size|flavor'  or  'name|a,b,c,d' */
    memset(bc, 0, sizeof *bc);
    const char *bar = strchr(spec, '|');
    if (!bar) die("bad --case '%s'", spec);
    size_t n = (size_t)(bar - spec);
    if (n >= sizeof bc->name) n = sizeof bc->name - 1;
    memcpy(bc->name, spec, n);
#if VA_SHAPE == SHAPE_INTS_U64
    const char *p = bar + 1;
    for (int i = 0; i < 4 && *p; i++) {
        bc->args[i] = strtoull(p, (char **)&p, 0);
        if (*p == ',') p++;
    }
#else
    char *end;
    bc->size = (size_t)strtoull(bar + 1, &end, 0);
    bc->flavor = *end == '|' ? (unsigned)strtoul(end + 1, NULL, 0) : 0;
    if (bc->flavor >= va_flavors()) die("--case '%s': flavor out of range", spec);
#endif
}

static int bench(const char *symbol, fn_t oracle, cand_t *cands, int ncand, bcase *cases, int ncase,
                 int samples, uint64_t sample_ns, uint64_t seed0) {
    (void)symbol;
    if (samples > MAX_SAMPLES) samples = MAX_SAMPLES;
    static double times[MAX_CANDS][MAX_SAMPLES];
    g.mode = "bench";

    for (int ci = 0; ci < ncase; ci++) {
        bcase *bc = &cases[ci];
        g.case_index = (uint64_t)ci;
        g.len = bc->size; g.flavor = bc->flavor; g.placement = PL_START;
        uint64_t inner[MAX_CANDS];
        int nsamp = samples;

#if VA_SHAPE == SHAPE_INTS_U64
        uint64_t *a = bc->args;
        memcpy(g.args, a, sizeof g.args);
        g.have_args = 1;
        g.phase = "oracle";
        uint64_t want = oracle(a[0], a[1], a[2], a[3]);
#define CALL(fn, v) (fn)(a[0], a[1], a[2], a[3])
#define WANT(v) want
#define VERIFY(k, v, got) ((got) == want)
#else
        /* two input variants, alternated, each verified against the oracle */
        region in[2];
        uint64_t want[2];
#if VA_SHAPE == SHAPE_BYTES_BYTES
        size_t cap = va_out_cap(bc->size);
        region expr[2], outr[MAX_CANDS];
        uint8_t *expb[2];
        for (int k = 0; k < ncand; k++) outr[k] = region_new(cap);
#endif
        for (int v = 0; v < 2; v++) {
            va_rng r;
            va_seed(&r, mix64(seed0, (uint64_t)ci * 2 + (uint64_t)v));
            in[v] = region_new(bc->size);
            g.in_ptr = in[v].lo; g.in_len = bc->size;
            g.phase = "gen";
            va_gen(&r, in[v].lo, bc->size, bc->flavor);
            region_prot(&in[v], PROT_READ);
            g.phase = "oracle";
#if VA_SHAPE == SHAPE_BYTES_U64
            want[v] = oracle(in[v].lo, bc->size);
#else
            expr[v] = region_new(cap);
            expb[v] = region_place(&expr[v], cap, PL_END, 0);
            want[v] = oracle(in[v].lo, bc->size, expb[v]);
#endif
        }
#if VA_SHAPE == SHAPE_BYTES_U64
#define CALL(fn, v) (fn)(in[v].lo, bc->size)
#define VERIFY(k, v, got) ((got) == want[v])
#else
#define CALL(fn, v) (fn)(in[v].lo, bc->size, outr[k].lo)
#define VERIFY(k, v, got) ((got) == want[v] && memcmp(outr[k].lo, expb[v], (size_t)want[v]) == 0)
#endif
#define WANT(v) want[v]
#endif

        /* calibrate the inner repeat count so one sample lasts about sample_ns */
        double slowest = 0;
        for (int k = 0; k < ncand; k++) {
            fn_t fn = cands[k].fn;
            g.cand = cands[k].name; g.cand_path = cands[k].path; g.phase = "candidate";
#if VA_SHAPE != SHAPE_INTS_U64
            g.in_ptr = in[0].lo; g.in_len = bc->size;
#endif
#if VA_SHAPE == SHAPE_BYTES_BYTES
            g.out_ptr = outr[k].lo; g.out_cap = cap;
#endif
            uint64_t n = 1;
            double per;
            for (;;) {
                uint64_t acc = 0, t0 = now_ns();
                for (uint64_t i = 0; i < n; i++) acc += (uint64_t)CALL(fn, 0);
                uint64_t dt = now_ns() - t0;
                g_sink += acc;
                if (dt >= sample_ns / 4 || n >= (1ull << 28)) {
                    per = (double)dt / (double)n;
                    break;
                }
                n *= 4;
            }
            if (per < 0.05) per = 0.05;
            uint64_t want_n = (uint64_t)((double)sample_ns / per + 0.5);
            inner[k] = want_n < 1 ? 1 : want_n;
            double one = per * (double)inner[k];
            if (one > slowest) slowest = one;
        }
        /* keep one (case) under ~2 s per candidate even for slow implementations */
        if (slowest * nsamp > 2e9) {
            nsamp = (int)(2e9 / slowest);
            if (nsamp < 5) nsamp = 5;
        }

        int ok[MAX_CANDS];
        for (int k = 0; k < ncand; k++) ok[k] = 1;
        for (int s = 0; s < nsamp; s++) {
            int v = s & 1;
            (void)v;
            for (int kk = 0; kk < ncand; kk++) {
                int k = (kk + s) % ncand; /* rotate order so no candidate always runs first */
                fn_t fn = cands[k].fn;
                g.cand = cands[k].name; g.cand_path = cands[k].path; g.phase = "candidate";
#if VA_SHAPE != SHAPE_INTS_U64
                g.in_ptr = in[v].lo; g.in_len = bc->size;
#endif
#if VA_SHAPE == SHAPE_BYTES_BYTES
                g.out_ptr = outr[k].lo; g.out_cap = cap;
#endif
                uint64_t n = inner[k], acc = 0, last = 0;
                uint64_t t0 = now_ns();
                for (uint64_t i = 0; i < n; i++) { last = (uint64_t)CALL(fn, v); acc += last; }
                uint64_t t1 = now_ns();
                g_sink += acc;
                times[k][s] = (double)(t1 - t0) / (double)n;
                if (!VERIFY(k, v, last)) ok[k] = 0;
            }
        }
        g.phase = "idle";

        for (int k = 0; k < ncand; k++) {
            double *t = times[k];
            qsort(t, (size_t)nsamp, sizeof(double), cmp_double);
            double mn = t[0], med = t[nsamp / 2], sum = 0;
            for (int s = 0; s < nsamp; s++) sum += t[s];
            dprintf(1,
                "{\"ev\":\"bench\",\"cand\":\"%s\",\"case\":\"%s\",\"size\":%zu,\"flavor\":%u,"
                "\"min_ns\":%.4f,\"median_ns\":%.4f,\"mean_ns\":%.4f,\"samples\":%d,\"inner\":%" PRIu64 ",\"correct\":%s}\n",
                cands[k].name, bc->name, bc->size, bc->flavor, mn, med, sum / nsamp, nsamp,
                inner[k], ok[k] ? "true" : "false");
        }
#if VA_SHAPE != SHAPE_INTS_U64
        for (int v = 0; v < 2; v++) munmap(in[v].base, in[v].total);
#if VA_SHAPE == SHAPE_BYTES_BYTES
        for (int v = 0; v < 2; v++) munmap(expr[v].base, expr[v].total);
        for (int k = 0; k < ncand; k++) munmap(outr[k].base, outr[k].total);
#endif
#endif
#undef CALL
#undef WANT
#undef VERIFY
    }
    return 0;
}

/* ---- call: run one explicit input --------------------------------------------- */

static int call_once(fn_t oracle, fn_t cand, const char *input_path, const char *args_spec) {
    uint64_t viol = 0;
    char regs[256];
    g.mode = "call";
    g.poison = POISON(1);
#if VA_SHAPE == SHAPE_INTS_U64
    (void)input_path;
    uint64_t a[4] = {0, 0, 0, 0};
    if (!args_spec) die("call: this task takes integers: use --args a,b,c,d");
    const char *p = args_spec;
    for (int i = 0; i < 4 && *p; i++) {
        a[i] = strtoull(p, (char **)&p, 0);
        if (*p == ',') p++;
    }
    memcpy(g.args, a, sizeof a);
    g.have_args = 1;
    g.phase = "oracle";
    uint64_t want = oracle(a[0], a[1], a[2], a[3]);
    g.phase = "candidate";
    alarm(20);
    uint64_t got = va_tramp((void *)cand, a[0], a[1], a[2], a[3], &viol, POISON(1));
    alarm(0);
    abi_list(viol, regs, sizeof regs);
    dprintf(1, "{\"ev\":\"call\",\"expected\":\"%" PRIu64 "\",\"got\":\"%" PRIu64 "\",\"match\":%s,\"clobbered\":[%s]}\n",
            want, got, want == got ? "true" : "false", regs);
    return want == got && !viol ? 0 : 1;
#else
    (void)args_spec;
    if (!input_path) die("call: this task takes bytes: use --input FILE");
    FILE *f = fopen(input_path, "rb");
    if (!f) die("cannot open %s: %s", input_path, strerror(errno));
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    size_t len = sz > 0 ? (size_t)sz : 0;
    region in = region_new(len);
    uint8_t *p = region_place(&in, len, PL_END, 0);
    if (len && fread(p, 1, len, f) != len) die("short read on %s", input_path);
    fclose(f);
    region_prot(&in, PROT_READ);
    g.in_ptr = p; g.in_len = len; g.len = len;
#if VA_SHAPE == SHAPE_BYTES_U64
    g.phase = "oracle";
    uint64_t want = oracle(p, len);
    g.phase = "candidate";
    alarm(20);
    uint64_t got = va_tramp((void *)cand, (uint64_t)(uintptr_t)p, len, 0x5151, 0x5252, &viol, POISON(1));
    alarm(0);
    abi_list(viol, regs, sizeof regs);
    dprintf(1, "{\"ev\":\"call\",\"len\":%zu,\"expected\":\"%" PRIu64 "\",\"got\":\"%" PRIu64 "\",\"match\":%s,\"clobbered\":[%s]}\n",
            len, want, got, want == got ? "true" : "false", regs);
    return want == got && !viol ? 0 : 1;
#else
    size_t cap = va_out_cap(len);
    region er = region_new(cap), orr = region_new(cap);
    uint8_t *eo = region_place(&er, cap, PL_END, 0), *dst = region_place(&orr, cap, PL_END, 0);
    g.phase = "oracle";
    g.out_ptr = eo; g.out_cap = cap;
    size_t want = oracle(p, len, eo);
    g.phase = "candidate";
    g.out_ptr = dst;
    alarm(20);
    size_t got = (size_t)va_tramp((void *)cand, (uint64_t)(uintptr_t)p, len, (uint64_t)(uintptr_t)dst, 0x5252,
                                  &viol, POISON(1));
    alarm(0);
    int same = got == want && memcmp(eo, dst, want) == 0;
    size_t diff = 0;
    if (got == want) while (diff < want && eo[diff] == dst[diff]) diff++;
    abi_list(viol, regs, sizeof regs);
    dprintf(1, "{\"ev\":\"call\",\"len\":%zu,\"expected_len\":%zu,\"got_len\":%zu,\"match\":%s,\"first_diff_at\":%zu,"
               "\"expected_hex\":\"%s\",\"got_hex\":\"%s\",\"clobbered\":[%s]}\n",
            len, want, got, same ? "true" : "false", diff, hex(eo, want, 128),
            hex(dst, got <= cap ? got : cap, 128), regs);
    return same && !viol ? 0 : 1;
#endif
#endif
}

/* ---- main --------------------------------------------------------------------- */

int main(int argc, char **argv) {
    g_page = (size_t)sysconf(_SC_PAGESIZE);
    if (argc < 2) die("usage: driver info|check|bench|call ...");
    const char *mode = argv[1];

    if (strcmp(mode, "info") == 0) {
        dprintf(1, "{\"ev\":\"info\",\"shape\":%d,\"page_size\":%zu,\"flavors\":[", VA_SHAPE, g_page);
        for (unsigned f = 0; f < va_flavors(); f++)
            dprintf(1, "%s\"%s\"", f ? "," : "", va_flavor_name(f));
        dprintf(1, "]}\n");
        return 0;
    }

    const char *symbol = NULL, *oracle_path = NULL, *input_path = NULL, *args_spec = NULL;
    static cand_t cands[MAX_CANDS];
    static bcase cases[MAX_CASES];
    int ncand = 0, ncase = 0, samples = 41;
    uint64_t seed = 1, random_n = 2000, sample_us = 400;
    size_t small_max = 160, max_size = 100000, large_size = (3u << 20) + 13;
    unsigned timeout = 5;

    for (int i = 2; i < argc; i++) {
        const char *a = argv[i];
#define ARG() (i + 1 < argc ? argv[++i] : (die("%s needs a value", a), ""))
        if (!strcmp(a, "--symbol")) symbol = ARG();
        else if (!strcmp(a, "--oracle")) oracle_path = ARG();
        else if (!strcmp(a, "--cand")) {
            if (ncand >= MAX_CANDS) die("too many candidates");
            char *spec = strdup(ARG());
            char *eq = strchr(spec, '=');
            if (eq) { *eq = 0; cands[ncand].name = spec; cands[ncand].path = eq + 1; }
            else { cands[ncand].name = "candidate"; cands[ncand].path = spec; }
            ncand++;
        }
        else if (!strcmp(a, "--case")) {
            if (ncase >= MAX_CASES) die("too many cases");
            parse_case(ARG(), &cases[ncase++]);
        }
        else if (!strcmp(a, "--seed")) seed = strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--random")) random_n = strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--small-max")) small_max = (size_t)strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--max-size")) max_size = (size_t)strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--large-size")) large_size = (size_t)strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--timeout")) timeout = (unsigned)strtoul(ARG(), NULL, 0);
        else if (!strcmp(a, "--samples")) samples = (int)strtol(ARG(), NULL, 0);
        else if (!strcmp(a, "--sample-us")) sample_us = strtoull(ARG(), NULL, 0);
        else if (!strcmp(a, "--dump")) g.dump_path = ARG();
        else if (!strcmp(a, "--input")) input_path = ARG();
        else if (!strcmp(a, "--args")) args_spec = ARG();
        else die("unknown option %s", a);
#undef ARG
    }
    if (!symbol || !oracle_path || ncand == 0) die("--symbol, --oracle and --cand are required");

#if defined(__APPLE__)
    /* ask for a performance core */
    pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE, 0);
#endif

    fn_t oracle = (fn_t)load_fn(oracle_path, symbol);
    for (int k = 0; k < ncand; k++) cands[k].fn = (fn_t)load_fn(cands[k].path, symbol);
    install_handlers();
    g.mode = mode;

    if (strcmp(mode, "check") == 0) {
        ctx_t cx;
        memset(&cx, 0, sizeof cx);
        cx.oracle = oracle;
        cx.cand = cands[0].fn;
        cx.timeout = timeout;
        g.cand = cands[0].name;
        g.cand_path = cands[0].path;
#if VA_SHAPE != SHAPE_INTS_U64
        size_t biggest = large_size > max_size ? large_size : max_size;
        cx.in = region_new(biggest);
#if VA_SHAPE == SHAPE_BYTES_BYTES
        cx.out = region_new(va_out_cap(biggest));
        cx.exp = region_new(va_out_cap(biggest));
#endif
#endif
        uint64_t t0 = now_ns();
        int failed = fuzz(&cx, seed, small_max, max_size, large_size, random_n);
        dprintf(1, "{\"ev\":\"check_done\",\"cand\":\"%s\",\"ok\":%s,\"cases\":%" PRIu64 ",\"seed\":%" PRIu64 ",\"ms\":%.1f}\n",
                g.cand, failed ? "false" : "true", cx.cases, seed, (double)(now_ns() - t0) / 1e6);
        return failed ? 1 : 0;
    }
    if (strcmp(mode, "bench") == 0) {
        if (ncase == 0) die("bench needs at least one --case");
        return bench(symbol, oracle, cands, ncand, cases, ncase, samples, sample_us * 1000, seed);
    }
    if (strcmp(mode, "call") == 0) return call_once(oracle, cands[0].fn, input_path, args_spec);
    die("unknown mode %s", mode);
    return 2;
}
