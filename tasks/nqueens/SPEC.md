# nqueens

```c
uint64_t nqueens(uint64_t n);
```

Return the number of ways to place `n` queens on an `n` x `n` chessboard so that no two
attack each other (no shared row, column or diagonal).

Known values: `nqueens(0) = 1`, `nqueens(1) = 1`, `nqueens(2) = 0`, `nqueens(3) = 0`,
`nqueens(4) = 2`, `nqueens(8) = 92`.

- `n` is at most 16 in every test and benchmark.

## Rules of this task

This task exists to compare the *same search* across implementations, so:

- **Count by exhaustive backtracking search.** Place one queen per row, tracking the
  attacked columns and diagonals, and count every complete placement individually.
- **No precomputed answers** and no table of results for particular `n`.
- **No symmetry reductions** (for example, searching half of the first row and
  doubling). They are valid mathematics, but every language could do the same; the
  point here is how fast the machine code runs the search.

Anything at the machine level is fair: register allocation, removing recursion,
unrolling, specializing the last rows, branchless bit tricks, and so on.
