# mandelbrot

```c
uint64_t mandelbrot(uint64_t width, uint64_t height, uint64_t max_iter);
```

For every pixel of a `width` x `height` grid, count how many iterations of
`z = z*z + c` it takes to escape (capped at `max_iter`), and return the **sum of all the
counts**. The grid covers the square `[-2, 1) x [-1.5, 1.5)`.

The result must be **bit-exact**, so the arithmetic is pinned down completely. All
values are IEEE-754 binary64 (`double`), round-to-nearest-even, and every operation
below is a separate correctly-rounded operation: **no fused multiply-add**.

```
dx = 3.0 / (double)width
dy = 3.0 / (double)height
total = 0
for py in 0 .. height-1:
    ci = -1.5 + (double)py * dy
    for px in 0 .. width-1:
        cr = -2.0 + (double)px * dx
        zr = 0.0; zi = 0.0; n = 0
        while n < max_iter:
            zr2 = zr * zr
            zi2 = zi * zi
            if zr2 + zi2 > 4.0: break
            zi = (2.0 * zr * zi) + ci
            zr = (zr2 - zi2) + cr
            n = n + 1
        total = total + n
return total
```

- If `width == 0` or `height == 0` the result is 0. If `max_iter == 0` the result is 0.
- Pixels may be processed in any order and several at a time, but each pixel's count
  must be exactly what the loop above gives: a pixel stops counting at the first
  iteration where `zr2 + zi2 > 4.0`.
- Multiplying by 2.0 is exact, so `2.0 * zr * zi` may be computed as `(zr * zi) + (zr * zi)`
  or `(zr + zr) * zi`.
- Inputs are small enough that `total` cannot overflow 64 bits; `width`, `height` < 2^20.
