/* wordcount -- input generators. */
#include "va_kit.h"

static const char *names[] = {"prose", "random-bytes", "all-whitespace", "no-whitespace",
                              "alternating", "long-runs", "boundary-bytes"};

unsigned va_flavors(void) { return 7; }
const char *va_flavor_name(unsigned f) { return names[f]; }

void va_gen(va_rng *r, uint8_t *buf, size_t len, unsigned flavor) {
    static const uint8_t ws[] = {' ', '\t', '\n', '\v', '\f', '\r'};
    /* bytes that sit right next to the whitespace set, plus their high-bit twins */
    static const uint8_t edge[] = {0x00, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x1F, 0x20, 0x21,
                                   0x7F, 0x80, 0x88, 0x89, 0x8A, 0x8D, 0x8E, 0xA0, 0xA1, 0xFF, 'a'};
    size_t i = 0;
    switch (flavor) {
    case 0: /* prose: words of 1-12 letters, mostly single spaces, some newlines */
        while (i < len) {
            size_t w = (size_t)va_range(r, 1, 12);
            for (size_t k = 0; k < w && i < len; k++) buf[i++] = (uint8_t)('a' + va_below(r, 26));
            if (i < len) buf[i++] = va_chance(r, 1, 12) ? '\n' : ' ';
            if (i < len && va_chance(r, 1, 40)) buf[i++] = ' ';
        }
        break;
    case 1:
        va_fill_random(r, buf, len);
        break;
    case 2:
        va_fill_from(r, buf, len, ws, sizeof ws);
        break;
    case 3:
        for (; i < len; i++) buf[i] = (uint8_t)('!' + va_below(r, 94));
        break;
    case 4: /* densest possible: a word every two bytes */
        for (; i < len; i++) buf[i] = (i & 1) ? ' ' : 'x';
        break;
    case 5: /* long runs of each class, lengths up to ~600 */
        while (i < len) {
            size_t run = (size_t)va_range(r, 1, va_chance(r, 1, 4) ? 600 : 40);
            int space = (int)va_below(r, 2);
            for (size_t k = 0; k < run && i < len; k++)
                buf[i++] = space ? ws[va_below(r, sizeof ws)] : (uint8_t)('A' + va_below(r, 26));
        }
        break;
    default:
        va_fill_from(r, buf, len, edge, sizeof edge);
        break;
    }
}
