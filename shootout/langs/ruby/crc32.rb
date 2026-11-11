# frozen_string_literal: true

# crc32 kernel (Ruby): port of tasks/crc32/ref.c, the textbook table-driven CRC-32
# with one table lookup per input byte.
module ShootoutKernel
  # The 256-entry table for the reflected polynomial 0xEDB88320 (the same values as the
  # literal table in ref.c), built once when the file is loaded.
  CRC_TABLE = Array.new(256) do |n|
    c = n
    8.times { c = c.odd? ? 0xEDB88320 ^ (c >> 1) : c >> 1 }
    c
  end.freeze

  def self.run(data)
    table = CRC_TABLE
    crc = 0xFFFFFFFF
    data.each_byte do |b|
      crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
    end
    crc ^ 0xFFFFFFFF
  end

  def self.digest
    0
  end
end
