/* va_kit.h -- the small C interface between a vibe-assembly task and the test driver.
 *
 * A task supplies two C files:
 *   ref.c  the reference implementation (the oracle). Plain, obviously-correct C.
 *   gen.c  input generators: how to make test inputs for the function.
 *
 * The driver (driver.c) does everything else: guard pages, differential fuzzing,
 * the ABI-checking trampoline, crash reports and timing.
 *
 * Shapes (the C signature every implementation of a task must have):
 *
 *   bytes_to_u64    uint64_t f(const uint8_t *buf, size_t len);
 *   bytes_to_bytes  size_t   f(const uint8_t *src, size_t len, uint8_t *dst);
 *                   dst has room for exactly va_out_cap(len) bytes; returns bytes written.
 *   ints_to_u64     uint64_t f(uint64_t a, uint64_t b, uint64_t c, uint64_t d);
 *                   (a task uses the first `nargs` of them)
 */
#ifndef VA_KIT_H
#define VA_KIT_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ---- deterministic RNG (xoshiro256**, seeded with splitmix64) ---------------- */

typedef struct { uint64_t s[4]; } va_rng;

static inline uint64_t va_rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

static inline uint64_t va_splitmix(uint64_t *x) {
    uint64_t z = (*x += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

static inline void va_seed(va_rng *r, uint64_t seed) {
    for (int i = 0; i < 4; i++) r->s[i] = va_splitmix(&seed);
}

static inline uint64_t va_next(va_rng *r) {
    uint64_t *s = r->s;
    uint64_t result = va_rotl(s[1] * 5, 7) * 9;
    uint64_t t = s[1] << 17;
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
    s[2] ^= t;
    s[3] = va_rotl(s[3], 45);
    return result;
}

/* Uniform integer in [0, n). n must be > 0. */
static inline uint64_t va_below(va_rng *r, uint64_t n) {
    return (uint64_t)(((__uint128_t)va_next(r) * n) >> 64);
}

/* Uniform integer in [lo, hi] inclusive. */
static inline uint64_t va_range(va_rng *r, uint64_t lo, uint64_t hi) {
    return lo + va_below(r, hi - lo + 1);
}

/* True with probability num/den. */
static inline int va_chance(va_rng *r, uint64_t num, uint64_t den) {
    return va_below(r, den) < num;
}

static inline void va_fill_random(va_rng *r, uint8_t *buf, size_t len) {
    size_t i = 0;
    for (; i + 8 <= len; i += 8) { uint64_t v = va_next(r); memcpy(buf + i, &v, 8); }
    if (i < len) { uint64_t v = va_next(r); memcpy(buf + i, &v, len - i); }
}

/* Every byte drawn uniformly from `alphabet`. */
static inline void va_fill_from(va_rng *r, uint8_t *buf, size_t len,
                                const uint8_t *alphabet, size_t n) {
    for (size_t i = 0; i < len; i++) buf[i] = alphabet[va_below(r, n)];
}

/* ---- what a task's gen.c provides ------------------------------------------- */

/* Number of input "flavors" (distributions). Flavor 0 is the typical input and is
 * what benchmarks use unless they say otherwise; the others should be adversarial. */
unsigned va_flavors(void);
const char *va_flavor_name(unsigned flavor);

/* bytes_to_u64 and bytes_to_bytes: fill buf[0..len) for the given flavor. */
void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor);

/* bytes_to_bytes only: exact capacity of dst for an input of `len` bytes. */
size_t va_out_cap(size_t len);

/* ints_to_u64 only: produce one argument tuple. Keep it cheap enough that the
 * reference runs in well under a millisecond: the fuzzer calls this thousands of times. */
void va_gen_args(va_rng *r, uint64_t args[4], unsigned flavor);

#endif /* VA_KIT_H */
