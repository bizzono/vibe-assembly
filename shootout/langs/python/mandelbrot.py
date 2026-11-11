"""mandelbrot kernel (Python): port of tasks/mandelbrot/ref.c.

Python floats are IEEE-754 doubles and every * + - below is its own correctly-rounded
operation (no fused multiply-add), which is what the contract requires. The operation
order is the reference's."""


def mandelbrot(width, height, max_iter):
    total = 0
    if width == 0 or height == 0:
        return 0
    dx = 3.0 / width
    dy = 3.0 / height
    for py in range(height):
        ci = -1.5 + py * dy
        for px in range(width):
            cr = -2.0 + px * dx
            zr = 0.0
            zi = 0.0
            n = 0
            while n < max_iter:
                zr2 = zr * zr
                zi2 = zi * zi
                if zr2 + zi2 > 4.0:
                    break
                zi = 2.0 * zr * zi + ci
                zr = zr2 - zi2 + cr
                n += 1
            total += n
    return total


def run(data):
    """The input is width, height, max_iter as little-endian u32."""
    if len(data) < 12:
        return 0
    width = int.from_bytes(data[0:4], "little")
    height = int.from_bytes(data[4:8], "little")
    max_iter = int.from_bytes(data[8:12], "little")
    return mandelbrot(width, height, max_iter)


def digest():
    return 0
