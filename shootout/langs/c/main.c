/* Shootout driver (C). See shootout/PROTOCOL.md. */
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

uint64_t run(const uint8_t *data, size_t len);
uint64_t digest(void);

static uint64_t now_ns(void) {
#ifdef __APPLE__
    return clock_gettime_nsec_np(CLOCK_UPTIME_RAW);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
#endif
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <input-file> <min_ms>\n", argv[0]);
        return 2;
    }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 2; }
    fseek(f, 0, SEEK_END);
    size_t len = (size_t)ftell(f);
    fseek(f, 0, SEEK_SET);
    uint8_t *data = malloc(len ? len : 1);
    if (!data || fread(data, 1, len, f) != len) { fprintf(stderr, "read failed\n"); return 2; }
    fclose(f);
    uint64_t min_ns = strtoull(argv[2], NULL, 10) * 1000000ull;

    uint64_t result = 0, best = UINT64_MAX, total = 0, calls = 0;
    if (min_ns == 0) { /* cold mode: one call, no digest */
        uint64_t t0 = now_ns();
        result = run(data, len);
        best = now_ns() - t0;
        printf("RESULT %" PRIu64 " 0 %" PRIu64 " 1\n", result, best);
        return 0;
    } else {
        uint64_t warm = run(data, len);
        while (calls < 3 || (total < min_ns && calls < 1000000)) {
            uint64_t t0 = now_ns();
            result = run(data, len);
            uint64_t dt = now_ns() - t0;
            if (result != warm) { fprintf(stderr, "result changed between calls\n"); return 3; }
            if (dt < best) best = dt;
            total += dt;
            calls++;
        }
    }
    printf("RESULT %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n", result, digest(), best, calls);
    return 0;
}
