/* base64_encode -- reference implementation (the oracle). See SPEC.md. */
#include <stddef.h>
#include <stdint.h>

static const char alphabet[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

size_t base64_encode(const uint8_t *src, size_t len, uint8_t *dst) {
    size_t i = 0, o = 0;
    for (; i + 3 <= len; i += 3) {
        uint32_t v = (uint32_t)src[i] << 16 | (uint32_t)src[i + 1] << 8 | src[i + 2];
        dst[o++] = (uint8_t)alphabet[v >> 18];
        dst[o++] = (uint8_t)alphabet[(v >> 12) & 63];
        dst[o++] = (uint8_t)alphabet[(v >> 6) & 63];
        dst[o++] = (uint8_t)alphabet[v & 63];
    }
    if (len - i == 1) {
        uint32_t v = (uint32_t)src[i] << 16;
        dst[o++] = (uint8_t)alphabet[v >> 18];
        dst[o++] = (uint8_t)alphabet[(v >> 12) & 63];
        dst[o++] = '=';
        dst[o++] = '=';
    } else if (len - i == 2) {
        uint32_t v = (uint32_t)src[i] << 16 | (uint32_t)src[i + 1] << 8;
        dst[o++] = (uint8_t)alphabet[v >> 18];
        dst[o++] = (uint8_t)alphabet[(v >> 12) & 63];
        dst[o++] = (uint8_t)alphabet[(v >> 6) & 63];
        dst[o++] = '=';
    }
    return o;
}
