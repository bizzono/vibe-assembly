/* utf8_validate -- input generators. Half of the flavors are valid UTF-8, half are
 * "almost valid": one defect, placed where vectorized validators tend to slip. */
#include "va_kit.h"

static const char *names[] = {"mixed-valid", "ascii", "multibyte-valid", "one-corruption",
                              "random-bytes", "valid-edges", "one-bad-edge", "truncated-tail"};

unsigned va_flavors(void) { return 8; }
const char *va_flavor_name(unsigned f) { return names[f]; }

static size_t put_cp(uint8_t *p, uint32_t cp) {
    if (cp < 0x80) { p[0] = (uint8_t)cp; return 1; }
    if (cp < 0x800) { p[0] = (uint8_t)(0xC0 | (cp >> 6)); p[1] = (uint8_t)(0x80 | (cp & 0x3F)); return 2; }
    if (cp < 0x10000) {
        p[0] = (uint8_t)(0xE0 | (cp >> 12)); p[1] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F));
        p[2] = (uint8_t)(0x80 | (cp & 0x3F));
        return 3;
    }
    p[0] = (uint8_t)(0xF0 | (cp >> 18)); p[1] = (uint8_t)(0x80 | ((cp >> 12) & 0x3F));
    p[2] = (uint8_t)(0x80 | ((cp >> 6) & 0x3F)); p[3] = (uint8_t)(0x80 | (cp & 0x3F));
    return 4;
}

/* a random code point whose encoding is exactly `k` bytes long */
static uint32_t rand_cp(va_rng *r, unsigned k) {
    uint32_t c;
    switch (k) {
    case 1: return (uint32_t)va_range(r, 0x20, 0x7E);
    case 2: return (uint32_t)va_range(r, 0x80, 0x7FF);
    case 3:
        do c = (uint32_t)va_range(r, 0x800, 0xFFFF); while (c >= 0xD800 && c <= 0xDFFF);
        return c;
    default: return (uint32_t)va_range(r, 0x10000, 0x10FFFF);
    }
}

/* fill exactly `len` bytes with valid UTF-8; w[k-1] = weight of k-byte sequences */
static void fill_valid(va_rng *r, uint8_t *buf, size_t len, const unsigned w[4]) {
    unsigned total = w[0] + w[1] + w[2] + w[3];
    size_t i = 0;
    while (i < len) {
        unsigned x = (unsigned)va_below(r, total), k = 1;
        while (k < 4 && x >= w[k - 1]) { x -= w[k - 1]; k++; }
        if (k > len - i) k = (unsigned)(len - i);
        i += put_cp(buf + i, rand_cp(r, k));
    }
}

static const unsigned W_MIXED[4] = {70, 14, 13, 3};
static const unsigned W_MULTI[4] = {5, 15, 55, 25};
static const unsigned W_ASCII[4] = {1, 0, 0, 0};

/* boundary sequences that ARE well-formed */
static const struct { uint8_t n, b[4]; } good[] = {
    {1, {0x00}}, {1, {0x7F}}, {2, {0xC2, 0x80}}, {2, {0xDF, 0xBF}}, {3, {0xE0, 0xA0, 0x80}},
    {3, {0xE0, 0xBF, 0xBF}}, {3, {0xE1, 0x80, 0x80}}, {3, {0xEC, 0xBF, 0xBF}}, {3, {0xED, 0x80, 0x80}},
    {3, {0xED, 0x9F, 0xBF}}, {3, {0xEE, 0x80, 0x80}}, {3, {0xEF, 0xBF, 0xBF}}, {4, {0xF0, 0x90, 0x80, 0x80}},
    {4, {0xF0, 0xBF, 0xBF, 0xBF}}, {4, {0xF1, 0x80, 0x80, 0x80}}, {4, {0xF3, 0xBF, 0xBF, 0xBF}},
    {4, {0xF4, 0x80, 0x80, 0x80}}, {4, {0xF4, 0x8F, 0xBF, 0xBF}},
};
/* boundary sequences that are NOT well-formed */
static const struct { uint8_t n, b[4]; } bad[] = {
    {1, {0x80}}, {1, {0xBF}}, {1, {0xC0}}, {1, {0xC1}}, {1, {0xF5}}, {1, {0xFF}}, {1, {0xFE}},
    {2, {0xC0, 0x80}}, {2, {0xC1, 0xBF}}, {2, {0xC2, 0x7F}}, {2, {0xC2, 0xC0}}, {2, {0xDF, 0x20}},
    {3, {0xE0, 0x80, 0x80}}, {3, {0xE0, 0x9F, 0xBF}}, {3, {0xED, 0xA0, 0x80}}, {3, {0xED, 0xBF, 0xBF}},
    {3, {0xE1, 0x80, 0x7F}}, {3, {0xE1, 0x7F, 0x80}}, {3, {0xEF, 0xBF, 0xC0}}, {2, {0xE1, 0x80}},
    {4, {0xF0, 0x80, 0x80, 0x80}}, {4, {0xF0, 0x8F, 0xBF, 0xBF}}, {4, {0xF4, 0x90, 0x80, 0x80}},
    {4, {0xF4, 0xBF, 0xBF, 0xBF}}, {4, {0xF5, 0x80, 0x80, 0x80}}, {4, {0xF1, 0x80, 0x80, 0x7F}},
    {4, {0xF1, 0x80, 0x7F, 0x80}}, {4, {0xF1, 0x7F, 0x80, 0x80}}, {3, {0xF1, 0x80, 0x80}}, {2, {0xF1, 0x80}},
    {4, {0xF8, 0x88, 0x80, 0x80}},
};
#define NGOOD (sizeof good / sizeof good[0])
#define NBAD (sizeof bad / sizeof bad[0])

static void fill_good_edges(va_rng *r, uint8_t *buf, size_t len) {
    size_t i = 0;
    while (i < len) {
        size_t k = (size_t)va_below(r, NGOOD);
        if (good[k].n > len - i) continue; /* there are 1-byte entries, so this terminates */
        memcpy(buf + i, good[k].b, good[k].n);
        i += good[k].n;
    }
}

/* a position biased toward the end of the buffer and toward 16/64-byte block edges */
static size_t tricky_pos(va_rng *r, size_t len) {
    size_t p = (size_t)va_below(r, len);
    switch (va_below(r, 4)) {
    case 0: return len - 1 - (size_t)va_below(r, len < 4 ? len : 4);
    case 1: p = (p & ~(size_t)15) + (size_t)va_below(r, 2) * 15; break;
    case 2: p = (p & ~(size_t)63) + (size_t)va_below(r, 2) * 63; break;
    default: break;
    }
    return p < len ? p : len - 1;
}

void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor) {
    switch (flavor) {
    case 0: fill_valid(r, buf, len, W_MIXED); break;
    case 1: fill_valid(r, buf, len, W_ASCII); break;
    case 2: fill_valid(r, buf, len, W_MULTI); break;
    case 3: /* valid text with a single byte overwritten */
        fill_valid(r, buf, len, va_chance(r, 1, 2) ? W_MIXED : W_ASCII);
        if (len) {
            size_t p = tricky_pos(r, len);
            switch (va_below(r, 4)) {
            case 0: buf[p] = (uint8_t)va_next(r); break;                 /* anything */
            case 1: buf[p] = (uint8_t)va_range(r, 0x80, 0xBF); break;    /* a continuation byte */
            case 2: buf[p] = (uint8_t)va_range(r, 0xC2, 0xF4); break;    /* a lead byte */
            default: {                                                   /* never valid anywhere */
                static const uint8_t never[] = {0xC0, 0xC1, 0xF5, 0xF8, 0xFB, 0xFE, 0xFF};
                buf[p] = never[va_below(r, sizeof never)];
            }
            }
        }
        break;
    case 4: va_fill_random(r, buf, len); break;
    case 5: fill_good_edges(r, buf, len); break;
    case 6: /* well-formed boundary sequences with one ill-formed one dropped in */
        fill_good_edges(r, buf, len);
        if (len) {
            size_t k = (size_t)va_below(r, NBAD);
            if (bad[k].n <= len) {
                size_t p = tricky_pos(r, len);
                if (p > len - bad[k].n) p = len - bad[k].n;
                memcpy(buf + p, bad[k].b, bad[k].n);
            } else {
                buf[len - 1] = 0xFF;
            }
        }
        break;
    default: { /* valid text whose last character is cut off by the end of the buffer */
        static const uint8_t cut[][3] = {{0xC3}, {0xE1}, {0xF1}, {0xE1, 0x80}, {0xF1, 0x80}, {0xF1, 0x80, 0x80},
                                         {0xE0, 0xA0}, {0xF0, 0x90, 0x80}, {0xF4, 0x8F, 0xBF}, {0xED, 0x9F}};
        static const uint8_t cut_n[] = {1, 1, 1, 2, 2, 3, 2, 3, 3, 2};
        size_t k = (size_t)va_below(r, sizeof cut_n);
        size_t t = cut_n[k] <= len ? cut_n[k] : 0;
        fill_valid(r, buf, len - t, va_chance(r, 1, 2) ? W_MIXED : W_ASCII);
        memcpy(buf + len - t, cut[k], t);
    }
    }
}
