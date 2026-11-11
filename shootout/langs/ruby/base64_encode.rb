# frozen_string_literal: true

# base64_encode kernel (Ruby): port of tasks/base64_encode/ref.c.
module ShootoutKernel
  ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".bytes.freeze
  PAD = 0x3D # '='

  @out = nil # a binary String, allocated on the first call and then reused
  @out_len = 0

  def self.encode(src, dst)
    alphabet = ALPHABET
    len = src.bytesize
    i = 0
    o = 0
    while i + 3 <= len
      v = src.getbyte(i) << 16 | src.getbyte(i + 1) << 8 | src.getbyte(i + 2)
      dst.setbyte(o, alphabet[v >> 18])
      dst.setbyte(o + 1, alphabet[(v >> 12) & 63])
      dst.setbyte(o + 2, alphabet[(v >> 6) & 63])
      dst.setbyte(o + 3, alphabet[v & 63])
      i += 3
      o += 4
    end
    if len - i == 1
      v = src.getbyte(i) << 16
      dst.setbyte(o, alphabet[v >> 18])
      dst.setbyte(o + 1, alphabet[(v >> 12) & 63])
      dst.setbyte(o + 2, PAD)
      dst.setbyte(o + 3, PAD)
      o += 4
    elsif len - i == 2
      v = src.getbyte(i) << 16 | src.getbyte(i + 1) << 8
      dst.setbyte(o, alphabet[v >> 18])
      dst.setbyte(o + 1, alphabet[(v >> 12) & 63])
      dst.setbyte(o + 2, alphabet[(v >> 6) & 63])
      dst.setbyte(o + 3, PAD)
      o += 4
    end
    o
  end

  def self.run(data)
    @out ||= ("\0".b * (4 * ((data.bytesize + 2) / 3)))
    @out_len = encode(data, @out)
  end

  # 64-bit FNV-1a of the bytes written by the last run. Not timed.
  def self.digest
    out = @out
    len = @out_len
    h = 0xcbf29ce484222325
    i = 0
    while i < len
      h = ((h ^ out.getbyte(i)) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
      i += 1
    end
    h
  end
end
