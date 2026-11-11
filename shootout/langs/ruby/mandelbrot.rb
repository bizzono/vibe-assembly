# frozen_string_literal: true

# mandelbrot kernel (Ruby): port of tasks/mandelbrot/ref.c.
# Ruby Floats are IEEE-754 doubles and every * + - below is its own correctly-rounded
# operation (no fused multiply-add), which is what the contract requires. The operation
# order is the reference's.
module ShootoutKernel
  def self.mandelbrot(width, height, max_iter)
    total = 0
    return 0 if width == 0 || height == 0
    dx = 3.0 / width
    dy = 3.0 / height
    py = 0
    while py < height
      ci = -1.5 + py * dy
      px = 0
      while px < width
        cr = -2.0 + px * dx
        zr = 0.0
        zi = 0.0
        n = 0
        while n < max_iter
          zr2 = zr * zr
          zi2 = zi * zi
          break if zr2 + zi2 > 4.0
          zi = 2.0 * zr * zi + ci
          zr = zr2 - zi2 + cr
          n += 1
        end
        total += n
        px += 1
      end
      py += 1
    end
    total
  end

  # The input is width, height, max_iter as little-endian u32.
  def self.run(data)
    return 0 if data.bytesize < 12
    width, height, max_iter = data.unpack("V3")
    mandelbrot(width, height, max_iter)
  end

  def self.digest
    0
  end
end
