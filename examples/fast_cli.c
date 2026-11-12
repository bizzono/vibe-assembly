// examples/fast_cli.c
//
// Shows how to link a real C application directly against the verified assembly
// routines in solutions/arm64-darwin/*.s with zero wrapper code.
//
// Build & run:
//   clang -O3 examples/fast_cli.c solutions/arm64-darwin/*.s -o /tmp/vibe-demo && /tmp/vibe-demo

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "../include/vibeasm.h"

static double now_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1e6;
}

int main(void) {
    const size_t size = 8 * 1024 * 1024; // 8 MiB buffer
    uint8_t *buf = (uint8_t *)malloc(size);
    uint8_t *b64 = (uint8_t *)malloc((size / 3 + 2) * 4);
    if (!buf || !b64) return 1;

    const char *phrase = "vibe-assembly verifies every register, page boundary, and edge case. ";
    size_t plen = strlen(phrase);
    for (size_t i = 0; i < size; i++) {
        buf[i] = (uint8_t)phrase[i % plen];
    }

    printf("======================================================================\n");
    printf("  vibe-assembly: calling verified arm64-darwin assembly from C\n");
    printf("======================================================================\n\n");

    double t0 = now_ms();
    int valid = utf8_validate(buf, size);
    double t_utf8 = now_ms() - t0;

    t0 = now_ms();
    size_t words = wordcount(buf, size);
    double t_wc = now_ms() - t0;

    t0 = now_ms();
    uint32_t crc = crc32_ieee(buf, size);
    double t_crc = now_ms() - t0;

    t0 = now_ms();
    size_t out_len = base64_encode(buf, 6 * 1024 * 1024, b64);
    double t_b64 = now_ms() - t0;

    t0 = now_ms();
    uint64_t msum = mandelbrot(512, 512, 200);
    double t_mand = now_ms() - t0;

    t0 = now_ms();
    uint64_t nq = nqueens(12);
    double t_nq = now_ms() - t0;

    printf("  1. utf8_validate (8 MiB) : valid=%d          in %6.3f ms (%5.1f GB/s)\n",
           valid, t_utf8, (size / 1e9) / (t_utf8 / 1e3));
    printf("  2. wordcount     (8 MiB) : %7zu words   in %6.3f ms (%5.1f GB/s)\n",
           words, t_wc, (size / 1e9) / (t_wc / 1e3));
    printf("  3. crc32_ieee    (8 MiB) : 0x%08x       in %6.3f ms (%5.1f GB/s)\n",
           crc, t_crc, (size / 1e9) / (t_crc / 1e3));
    printf("  4. base64_encode (6 MiB) : %7zu chars   in %6.3f ms (%5.1f GB/s)\n",
           out_len, t_b64, ((6.0 * 1024 * 1024) / 1e9) / (t_b64 / 1e3));
    printf("  5. mandelbrot  (512x512) : %7llu iters   in %6.3f ms\n",
           (unsigned long long)msum, t_mand);
    printf("  6. nqueens        (N=12) : %7llu boards  in %6.3f ms\n\n",
           (unsigned long long)nq, t_nq);

    free(buf);
    free(b64);
    return 0;
}
