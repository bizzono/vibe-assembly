/* nqueens -- reference implementation (the oracle). See SPEC.md.
 * The textbook bitmask backtracking search. */
#include <stdint.h>

static uint64_t place(uint32_t all, uint32_t cols, uint32_t diag_l, uint32_t diag_r) {
    if (cols == all) return 1;
    uint64_t count = 0;
    uint32_t free = all & ~(cols | diag_l | diag_r);
    while (free) {
        uint32_t bit = free & -free; /* lowest free square in this row */
        free ^= bit;
        count += place(all, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1);
    }
    return count;
}

uint64_t nqueens(uint64_t n) {
    if (n > 31) return 0;
    uint32_t all = (uint32_t)((1ull << n) - 1);
    return place(all, 0, 0, 0);
}
