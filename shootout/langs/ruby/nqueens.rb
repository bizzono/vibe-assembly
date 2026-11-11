# frozen_string_literal: true

# nqueens kernel (Ruby): port of tasks/nqueens/ref.c, the textbook bitmask
# backtracking search.
#
# The reference keeps the masks in uint32. Ruby Integers do not wrap, so the left
# diagonal mask may carry bits above bit 31 that C would have dropped; those bits lie
# outside `full` and are masked away when `free` is computed, so the search is the same.
module ShootoutKernel
  def self.place(full, cols, diag_l, diag_r)
    return 1 if cols == full
    count = 0
    free = full & ~(cols | diag_l | diag_r)
    while free != 0
      bit = free & -free # lowest free square in this row
      free ^= bit
      count += place(full, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1)
    end
    count
  end

  def self.nqueens(n)
    return 0 if n > 31
    place((1 << n) - 1, 0, 0, 0)
  end

  # The input is n as a little-endian u32.
  def self.run(data)
    n = data.bytesize >= 4 ? data.unpack("V")[0] : 0
    nqueens(n)
  end

  def self.digest
    0
  end
end
