"""nqueens kernel (Python): port of tasks/nqueens/ref.c, the textbook bitmask
backtracking search.

The reference keeps the masks in uint32. Python integers do not wrap, so the left
diagonal mask may carry bits above bit 31 that C would have dropped; those bits lie
outside `full` and are masked away when `free` is computed, so the search is the same."""


def place(full, cols, diag_l, diag_r):
    if cols == full:
        return 1
    count = 0
    free = full & ~(cols | diag_l | diag_r)
    while free:
        bit = free & -free  # lowest free square in this row
        free ^= bit
        count += place(full, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1)
    return count


def nqueens(n):
    if n > 31:
        return 0
    return place((1 << n) - 1, 0, 0, 0)


def run(data):
    """The input is n as a little-endian u32."""
    n = int.from_bytes(data[0:4], "little") if len(data) >= 4 else 0
    return nqueens(n)


def digest():
    return 0
