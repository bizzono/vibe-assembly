/* wordcount -- reference implementation (the oracle). See SPEC.md. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static bool is_space(uint8_t c) {
    return c == ' ' || (c >= '\t' && c <= '\r'); /* space, \t \n \v \f \r */
}

uint64_t wordcount(const uint8_t *buf, size_t len) {
    uint64_t words = 0;
    bool in_word = false;
    for (size_t i = 0; i < len; i++) {
        if (is_space(buf[i])) {
            in_word = false;
        } else if (!in_word) {
            in_word = true;
            words++;
        }
    }
    return words;
}
